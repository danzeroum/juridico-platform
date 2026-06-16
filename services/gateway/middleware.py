from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import time
import logging

logger = logging.getLogger(__name__)

# Rate limit simples em memoria (substituir por Redis em producao)
_request_counts: dict = {}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting basico: 100 req/min por IP."""

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        current_minute = int(time.time() / 60)
        key = f"{client_ip}:{current_minute}"

        _request_counts[key] = _request_counts.get(key, 0) + 1

        if _request_counts[key] > 100:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit excedido. Maximo 100 req/min."}
            )

        response = await call_next(request)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Headers de seguranca obrigatorios."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
        return response
