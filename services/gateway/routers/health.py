"""Health check endpoints — públicos, sem autenticação.

- GET /health: liveness (o processo responde). Sempre 200.
- GET /ready: readiness (dependências alcançáveis). 503 se alguma dependência
  CONFIGURADA estiver fora — dependência não configurada (dev/teste) não falha.
"""
import os
from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["infra"])


@router.get(
    "/health",
    summary="Health check (liveness)",
    response_description="Status do gateway e dependências",
    responses={
        200: {
            "description": "Serviço saudável",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "service": "gateway",
                        "version": "0.2.0",
                        "timestamp": "2026-06-16T08:00:00+00:00",
                    }
                }
            },
        }
    },
)
async def health() -> dict:
    return {
        "status": "healthy",
        "service": "gateway",
        "version": "0.2.0",
        "timestamp": datetime.now(UTC).isoformat(),
    }


def _check_redis() -> str:
    if not os.getenv("REDIS_URL"):
        return "not_configured"
    try:
        from services.shared.redis_client import get_redis
        get_redis().ping()
        return "ok"
    except Exception as exc:  # noqa: BLE001 — qualquer falha = não pronto
        return f"fail: {type(exc).__name__}"


def _check_postgres() -> str:
    if not os.getenv("DATABASE_URL"):
        return "not_configured"
    try:
        # Engine efêmero e descartado: /ready é chamado por probes com baixa
        # frequência e não deve segurar pool próprio nem importar
        # services.shared.db (que cria engine global no import).
        from sqlalchemy import create_engine, text
        engine = create_engine(
            os.environ["DATABASE_URL"],
            connect_args={"connect_timeout": 5},
            pool_pre_ping=False,
        )
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        finally:
            engine.dispose()
        return "ok"
    except Exception as exc:  # noqa: BLE001
        return f"fail: {type(exc).__name__}"


@router.get(
    "/ready",
    summary="Readiness check (dependências)",
    description=(
        "Verifica conectividade com as dependências configuradas (Redis, "
        "PostgreSQL). Dependência sem variável de ambiente correspondente é "
        "reportada como `not_configured` e não derruba a prontidão — permite "
        "dev/teste sem stack completo. Use este endpoint como readiness probe "
        "(Traefik/K8s); use `/health` como liveness."
    ),
    responses={
        200: {
            "description": "Pronto para receber tráfego",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ready",
                        "checks": {"redis": "ok", "postgres": "ok"},
                        "timestamp": "2026-06-16T08:00:00+00:00",
                    }
                }
            },
        },
        503: {
            "description": "Alguma dependência configurada está inacessível",
            "content": {
                "application/json": {
                    "example": {
                        "status": "not_ready",
                        "checks": {"redis": "fail: ConnectionError", "postgres": "ok"},
                        "timestamp": "2026-06-16T08:00:00+00:00",
                    }
                }
            },
        },
    },
)
async def ready() -> JSONResponse:
    checks = {
        "redis": _check_redis(),
        "postgres": _check_postgres(),
    }
    is_ready = not any(v.startswith("fail") for v in checks.values())
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={
            "status": "ready" if is_ready else "not_ready",
            "checks": checks,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
