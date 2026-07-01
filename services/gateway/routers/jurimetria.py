"""
Jurimetria — Indicadores + Market Intelligence (produto-vitrine da fundação).

Expõe o feature store `jurimetria.indicador` (duração, congestionamento,
litigiosidade por tribunal/classe/assunto) e um relatório setorial agregado.

Governança: todos os dados são AGREGADOS e públicos — ZERO PII. O relatório de
Market Intelligence registra uma entrada no Decision Ledger (auditabilidade),
sem qualquer dado pessoal. Segue o template P2 do router LegalScore (JWT,
problem+json global, OTel, exemplos OpenAPI).
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from services.jurimetria import queries

try:
    from opentelemetry import trace as otel_trace
    _tracer = otel_trace.get_tracer("jurimetria")
    _OTEL = True
except ImportError:
    _OTEL = False
    _tracer = None  # type: ignore[assignment]

router = APIRouter(tags=["jurimetria"])


def _get_tenant(request: Request) -> str:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token JWT não contém tenant_id.",
        )
    return tenant_id


class MarketIntelligenceRequest(BaseModel):
    tribunal: str | None = Field(default=None, description="Sigla do tribunal (ex.: TJSP)")
    ramo: str | None = Field(default=None, description="Ramo do direito (opcional)")

    model_config = {"json_schema_extra": {"example": {"tribunal": "TJSP", "ramo": "EMPRESARIAL"}}}


@router.get(
    "/indicators",
    summary="Indicadores jurimétricos com filtros",
    responses={200: {"description": "Lista de indicadores agregados"}},
)
async def indicators(
    request: Request,
    tribunal: str | None = Query(default=None),
    classe: str | None = Query(default=None),
    assunto: str | None = Query(default=None),
    periodo: str | None = Query(default=None),
    fonte: str | None = Query(default=None, description="DATAJUD | ABJ | BLEND"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Any:
    _get_tenant(request)
    span = _tracer.start_as_current_span("jurimetria.indicators") if _OTEL else _noop_span()
    with span:
        rows = queries.get_indicators(tribunal, classe, assunto, periodo, fonte, limit, offset)
    return {"count": len(rows), "results": rows, "limit": limit, "offset": offset}


@router.get(
    "/tribunal/{tribunal}/congestion",
    summary="Taxa de congestionamento por classe/assunto de um tribunal",
)
async def congestion(tribunal: str, request: Request) -> Any:
    _get_tenant(request)
    rows = queries.get_congestion(tribunal)
    return {"tribunal": tribunal.upper(), "count": len(rows), "results": rows}


@router.get(
    "/classe/{classe}/duration",
    summary="Duração (mediana + IQR) por tribunal para uma classe TPU",
)
async def duration(classe: str, request: Request) -> Any:
    _get_tenant(request)
    rows = queries.get_duration(classe)
    return {"classe_tpu": classe, "count": len(rows), "results": rows}


@router.get(
    "/litigiosity",
    summary="Litigiosidade (volume) por tribunal, opcionalmente por assunto",
)
async def litigiosity(request: Request, assunto: str | None = Query(default=None)) -> Any:
    _get_tenant(request)
    rows = queries.get_litigiosity(assunto)
    return {"assunto_tpu": assunto, "count": len(rows), "results": rows}


@router.post(
    "/market-intelligence",
    summary="Relatório setorial agregado (Market Intelligence)",
    description=(
        "Gera um relatório de inteligência de mercado a partir de dados "
        "**agregados** (sem PII): volume, congestionamento, duração e provimento "
        "por classe/assunto. Registra entrada no Decision Ledger para auditabilidade."
    ),
    responses={
        200: {
            "description": "Relatório gerado",
            "content": {"application/json": {"example": {
                "request_id": "req_01abc",
                "tribunal": "TJSP",
                "total_processos": 152340,
                "n_segmentos": 42,
            }}},
        },
    },
)
async def market_intelligence(body: MarketIntelligenceRequest, request: Request) -> Any:
    tenant_id = _get_tenant(request)
    request_id = str(uuid.uuid4())
    span = _tracer.start_as_current_span("jurimetria.market_intelligence") if _OTEL else _noop_span()
    with span:
        report = queries.market_intelligence(body.tribunal, body.ramo)

    # Decision Ledger — relatório agregado, sem PII (subject_token ausente).
    try:
        _ledger_entry(tenant_id, request_id, body, report)
    except Exception:  # noqa: BLE001 — ledger indisponível não deve derrubar o relatório
        pass

    return {"request_id": request_id, **report}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ledger_entry(
    tenant_id: str, request_id: str, body: MarketIntelligenceRequest, report: dict[str, Any]
) -> None:
    """Registra a geração do relatório no Decision Ledger (sem PII)."""
    import os

    from services.shared.ledger.merkle import DecisionLedger

    if os.environ.get("DATABASE_URL"):
        from services.shared.ledger.merkle import PostgresDecisionLedger
        ledger: DecisionLedger = PostgresDecisionLedger(tenant_id)
    else:
        ledger = DecisionLedger()

    entry = ledger.add_entry(
        request_id=request_id,
        product="jurimetria-market-intelligence",
        inputs={"tribunal": body.tribunal, "ramo": body.ramo},
        outputs={"total_processos": report.get("total_processos"), "n_segmentos": report.get("n_segmentos")},
        sources=["jurimetria.indicador"],
        subject_token=None,  # relatório agregado — não há titular de dado pessoal
    )
    from services.shared.audit_log import log_ledger_write
    log_ledger_write(
        request_id=request_id,
        product="jurimetria-market-intelligence",
        tenant_id=tenant_id,
        entry_index=entry["entry_index"],
        has_subject_token=False,
    )


class _noop_span:
    def __enter__(self): return None
    def __exit__(self, *_): pass
