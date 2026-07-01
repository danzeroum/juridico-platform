"""
Demand Forecasting — projeção de volume de ações por tribunal/classe/assunto.

Consome a série histórica de jurimetria.indicador. Só dados agregados, sem PII.
Template P2 (JWT via _get_tenant, problem+json global, OTel opcional).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status

from services.forecasting import queries

router = APIRouter(tags=["forecasting"])


def _get_tenant(request: Request) -> str:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token JWT não contém tenant_id.",
        )
    return tenant_id


@router.get(
    "/demand",
    summary="Projeção de volume futuro de ações",
    description=(
        "Projeta o volume de ações para os próximos períodos a partir da série "
        "histórica jurimétrica. Heurística de tendência linear — não validada "
        "contra desfechos reais. Requer histórico suficiente (≥3 períodos)."
    ),
    responses={
        200: {"description": "Projeção calculada (ou status=insuficiente)"},
    },
)
async def demand(
    request: Request,
    tribunal: str = Query(..., description="Sigla do tribunal (ex.: TJSP)"),
    classe: str | None = Query(default=None),
    assunto: str | None = Query(default=None),
    horizonte: int = Query(default=3, ge=1, le=12),
) -> Any:
    _get_tenant(request)
    return queries.forecast_demand(tribunal, classe, assunto, horizonte)
