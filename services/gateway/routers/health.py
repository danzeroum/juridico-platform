"""Health check endpoint — público, sem autenticação."""
from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["infra"])


@router.get(
    "/health",
    summary="Health check",
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
