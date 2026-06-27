"""
Middlewares do gateway:
- SecurityHeadersMiddleware: headers de segurança obrigatórios.
- JWTAuthMiddleware: valida JWT RS256 e injeta tenant_id/role no request state.
- RateLimitMiddleware: rate limiting por tenant (não por IP) via Redis.

ISOLAMENTO DE TENANT (RLS + PgBouncer):
    Em pool_mode: transaction, a conexão de servidor é reutilizada.
    SET LOCAL (não SET) garante que app.tenant_id é revertido no COMMIT.
    Usar get_db_connection(tenant_id) como dependência FastAPI — ela envolve
    SET LOCAL + query dentro de BEGIN...COMMIT automaticamente.

ORDEM DOS MIDDLEWARES (do mais externo para o mais interno):
    1. SecurityHeadersMiddleware
    2. JWTAuthMiddleware
    3. Routers (rate limiting via SlowAPI no nível de rota)
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Rotas públicas que não exigem JWT
_PUBLIC_PATHS = {
    "/health",
    "/api/v1/health",
    "/.well-known/jwks.json",
    "/api/v1/auth/token",
    "/openapi.json",
    "/docs",
    "/redoc",
}

# Rate limit por tenant via Redis (INCR + TTL) — funciona entre réplicas.
_RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "100"))
# Se o Redis cair: por padrão FAIL-OPEN (preserva disponibilidade) com aviso;
# defina RATE_LIMIT_FAIL_CLOSED=true para rejeitar (503) quando o limitador
# estiver indisponível.
_RATE_LIMIT_FAIL_CLOSED = os.getenv("RATE_LIMIT_FAIL_CLOSED", "false").strip().lower() == "true"

# Circuit breaker: ao falhar (Redis fora), evita pagar o timeout de conexão a
# cada request — abre o circuito por _REDIS_COOLDOWN segundos.
_REDIS_COOLDOWN = 30.0
_redis_down_until = 0.0


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Headers de segurança obrigatórios em todas as respostas."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    Valida Bearer token JWT RS256.
    Injeta request.state.tenant_id, request.state.user_id, request.state.role.
    Retorna 401 com problem+json para rotas protegidas sem token válido.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        path = request.url.path

        # Rotas públicas: skip JWT
        if path in _PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return _problem_json(
                status=401,
                title="Não autenticado",
                detail="Header Authorization com Bearer token obrigatório.",
                instance=path,
            )

        token = auth_header[len("Bearer "):]
        try:
            from services.gateway.auth.jwt import validate_token
            payload = validate_token(token)
        except Exception as exc:
            logger.warning("JWT inválido para %s: %s", path, exc)
            return _problem_json(
                status=401,
                title="Token inválido ou expirado",
                detail=str(exc),
                instance=path,
            )

        request.state.user_id = payload.get("sub")
        request.state.tenant_id = payload.get("tenant_id")
        request.state.role = payload.get("role", "viewer")

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting por tenant (não por IP) — `RATE_LIMIT_PER_MIN` (100) por padrão.

    Contador em Redis: `INCR ratelimit:{tenant}:{minuto}` com `EXPIRE 60s`. Como
    o estado é compartilhado, o limite vale para o cluster inteiro (não por
    processo). Se o Redis estiver indisponível, ver `_RATE_LIMIT_FAIL_CLOSED`.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        global _redis_down_until

        client_host = request.client.host if request.client else "anon"
        tenant_id = getattr(request.state, "tenant_id", None) or client_host
        now = time.time()
        current_minute = int(now // 60)
        key = f"ratelimit:{tenant_id}:{current_minute}"

        # Circuito aberto: Redis fora há pouco — não tenta de novo até o cooldown.
        if now < _redis_down_until:
            return await self._on_limiter_unavailable(request, call_next)

        try:
            from services.shared.redis_client import get_redis

            redis = get_redis()
            count = redis.incr(key)
            if count == 1:
                redis.expire(key, 60)
        except Exception as exc:
            _redis_down_until = now + _REDIS_COOLDOWN
            logger.warning("Rate limiter (Redis) indisponível por %ss: %s", int(_REDIS_COOLDOWN), exc)
            return await self._on_limiter_unavailable(request, call_next)

        if count > _RATE_LIMIT_PER_MIN:
            return _problem_json(
                status=429,
                title="Rate limit excedido",
                detail=f"Máximo de {_RATE_LIMIT_PER_MIN} requisições por minuto por tenant.",
                instance=request.url.path,
                extra={"Retry-After": "60"},
            )

        return await call_next(request)

    async def _on_limiter_unavailable(self, request: Request, call_next: Any) -> Response:
        """Redis fora: rejeita (fail-closed) ou segue sem limite (fail-open)."""
        if _RATE_LIMIT_FAIL_CLOSED:
            return _problem_json(
                status=503,
                title="Limitador indisponível",
                detail="Rate limiter temporariamente indisponível.",
                instance=request.url.path,
                extra={"Retry-After": "5"},
            )
        return await call_next(request)


def _problem_json(
    status: int,
    title: str,
    detail: str,
    instance: str,
    extra: dict[str, str] | None = None,
) -> JSONResponse:
    """Contrato de erro RFC 9457 (application/problem+json)."""
    headers = {"Content-Type": "application/problem+json"}
    if extra:
        headers.update(extra)
    return JSONResponse(
        status_code=status,
        content={
            "type": f"https://juridico-platform/errors/{status}",
            "title": title,
            "status": status,
            "detail": detail,
            "instance": instance,
            "contract_version": "1.0",
        },
        headers=headers,
    )
