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

import time
import logging
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

# Rate limit por tenant em memória (substituir por Redis em produção)
_request_counts: dict[str, int] = {}
_DEFAULT_RATE_LIMIT = 100  # req/min por tenant


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
    Rate limiting por tenant (não por IP) — 100 req/min por tenant por padrão.
    Em produção: substituir o dict em memória por Redis INCR com TTL de 60s.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        tenant_id = getattr(request.state, "tenant_id", None) or request.client.host
        current_minute = int(time.time() / 60)
        key = f"{tenant_id}:{current_minute}"

        _request_counts[key] = _request_counts.get(key, 0) + 1
        if _request_counts[key] > _DEFAULT_RATE_LIMIT:
            return _problem_json(
                status=429,
                title="Rate limit excedido",
                detail=f"Máximo de {_DEFAULT_RATE_LIMIT} requisições por minuto por tenant.",
                instance=request.url.path,
                extra={"Retry-After": "60"},
            )

        response = await call_next(request)
        return response


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
