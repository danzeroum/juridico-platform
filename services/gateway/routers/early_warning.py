"""
Early Warning System — detecção de surtos de litigiosidade / congestionamento.

Lê séries de jurimetria.indicador e dispara gatilhos. Só dados agregados (sem PII).
Template P2. Os gatilhos podem alimentar a camada de alertas (AlertEnvelope) na borda.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status

from services.early_warning import queries

router = APIRouter(tags=["early-warning"])


def _get_tenant(request: Request) -> str:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token JWT não contém tenant_id.",
        )
    return tenant_id


@router.get(
    "/evaluate",
    summary="Avalia surtos/picos para um tribunal (opcionalmente por classe/assunto)",
    description=(
        "Detecta surto de volume (z-score / variação) e pico de congestionamento a "
        "partir da série histórica jurimétrica. Heurística."
    ),
)
async def evaluate(
    request: Request,
    tribunal: str = Query(..., description="Sigla do tribunal (ex.: TJSP)"),
    classe: str | None = Query(default=None),
    assunto: str | None = Query(default=None),
) -> Any:
    _get_tenant(request)
    return queries.evaluate(tribunal, classe, assunto)
