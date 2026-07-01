"""
Chamber Profiler — perfil estatístico AGREGADO de órgão julgador (tribunal/câmara).

LGPD: nunca perfila juiz individual. Grão atual: tribunal+classe (ver pendencias.md).
Template P2 (JWT via _get_tenant, problem+json global).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status

from services.chamber_profiler import queries

router = APIRouter(tags=["chamber-profiler"])


def _get_tenant(request: Request) -> str:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token JWT não contém tenant_id.",
        )
    return tenant_id


@router.get(
    "/tribunal/{tribunal}",
    summary="Perfil agregado de um órgão julgador (tribunal/câmara)",
    description=(
        "Retorna faixas de provimento, congestionamento e duração de um órgão, "
        "ponderadas por volume. AGREGADO — nunca por juiz individual (LGPD)."
    ),
)
async def profile(
    tribunal: str, request: Request, classe: str | None = Query(default=None)
) -> Any:
    _get_tenant(request)
    return queries.profile_tribunal(tribunal, classe)
