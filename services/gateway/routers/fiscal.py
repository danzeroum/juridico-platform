"""
FiscalEngine — Router (NCM + ICMS). Segue o template P2 do legalscore.py:
versionamento /api/v1/fiscal/..., problem+json global, Idempotency-Key, OTel,
JWT + rate limit por middleware, Decision Ledger com prova de inclusão.

Endpoints:
- POST /ncm/triage            triagem síncrona de um item (determinística)
- GET  /ncm/{codigo}          descrição oficial vigente
- GET  /icms/{ncm}/{uf}       alíquota interna efetiva + interestadual + DIFAL
- POST /spreadsheet/enrich    enriquecimento assíncrono (202 + polling)
- GET  /jobs/{job_id}         status do job
- GET  /audit/{request_id}    prova Merkle da triagem/lote
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, File, Header, HTTPException, Query, Request, UploadFile, status

from services.fiscal.repository import classify_one
from services.shared.contracts.fiscal import (
    UF,
    NcmTriageRequest,
    NcmTriageResult,
    SpreadsheetJobResponse,
)

try:
    from opentelemetry import trace as otel_trace
    _tracer = otel_trace.get_tracer("fiscal")
    _OTEL = True
except ImportError:
    _OTEL = False
    _tracer = None  # type: ignore[assignment]


@contextmanager
def _noop_span():
    yield None


router = APIRouter(tags=["fiscal"])

_MAX_UPLOAD_ROWS = 50_000


def _get_tenant(request: Request) -> str:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token JWT não contém tenant_id.")
    return tenant_id


def _get_ledger(tenant_id: str):
    import os
    if os.environ.get("DATABASE_URL"):
        from services.shared.ledger.merkle import PostgresDecisionLedger
        return PostgresDecisionLedger(tenant_id)
    from services.shared.ledger.merkle import DecisionLedger
    return DecisionLedger()


# ---------------------------------------------------------------------------
# POST /ncm/triage — triagem síncrona de um item
# ---------------------------------------------------------------------------
@router.post(
    "/ncm/triage",
    response_model=NcmTriageResult,
    summary="Triagem de NCM + ICMS de um item (determinística)",
)
async def triage(
    body: NcmTriageRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> NcmTriageResult:
    tenant_id = _get_tenant(request)
    request_id = f"fiscal_{uuid.uuid4().hex[:16]}"

    ctx = _tracer.start_as_current_span("fiscal.triage") if _OTEL else _noop_span()
    with ctx as span:
        if _OTEL and span:
            span.set_attribute("tenant.id", tenant_id)

        result = classify_one(body)

        # Decision Ledger — 1 entrada para a triagem individual (1:1).
        entry = _get_ledger(tenant_id).add_entry(
            request_id=request_id,
            product="fiscal",
            inputs={"descricao": body.descricao, "uf_o": body.uf_origem, "uf_d": body.uf_destino},
            outputs={
                "ncm": result.suggested_ncm.ncm_codigo if result.suggested_ncm else None,
                "interna_efetiva": result.icms.interna_efetiva_pct,
                "difal": result.icms.difal_pct,
            },
            sources=[c.value for c in ([result.suggested_ncm.fonte_regra] if result.suggested_ncm else [])],
        )
        return result.model_copy(update={"decision_proof": request_id, "sku_descricao": body.descricao}) \
            if entry else result


# ---------------------------------------------------------------------------
# GET /ncm/{codigo}
# ---------------------------------------------------------------------------
@router.get("/ncm/{codigo}", summary="Descrição oficial vigente de um NCM")
async def get_ncm(
    codigo: str,
    request: Request,
    data: Annotated[date | None, Query(description="Data de vigência (default: hoje)")] = None,
) -> dict[str, Any]:
    _get_tenant(request)
    if not (codigo.isdigit() and len(codigo) == 8):
        raise HTTPException(status_code=400, detail="NCM deve ter 8 dígitos numéricos.")
    from services.fiscal.repository import DbNcmSource
    from services.shared.tenant_db import get_engine

    with get_engine().connect() as conn:
        row = DbNcmSource(conn).get_ncm(codigo, data)
    if row is None:
        raise HTTPException(status_code=404, detail=f"NCM {codigo} não encontrado na base vigente.")
    return {"ncm_codigo": row["ncm_codigo"], "descricao": row["descricao"]}


# ---------------------------------------------------------------------------
# GET /icms/{ncm}/{uf}
# ---------------------------------------------------------------------------
@router.get("/icms/{ncm}/{uf}", summary="ICMS interno efetivo + interestadual + DIFAL")
async def get_icms(
    ncm: str,
    uf: str,
    request: Request,
    uf_origem: Annotated[str, Query(description="UF de origem (default: SP)")] = "SP",
    importado: Annotated[bool, Query()] = False,
    data: Annotated[date | None, Query()] = None,
) -> dict[str, Any]:
    _get_tenant(request)
    if uf.upper() not in UF.__members__ or uf_origem.upper() not in UF.__members__:
        raise HTTPException(status_code=400, detail="UF inválida.")
    from services.fiscal.repository import DbIcmsSource
    from services.fiscal.triage.icms_resolver import resolve_icms
    from services.shared.tenant_db import get_engine

    with get_engine().connect() as conn:
        interna = DbIcmsSource(conn).interna(uf.upper(), ncm, data)
    icms = resolve_icms(uf_origem.upper(), uf.upper(), interna, importado=importado)
    return icms.model_dump()


# ---------------------------------------------------------------------------
# POST /spreadsheet/enrich — assíncrono (202)
# ---------------------------------------------------------------------------
@router.post(
    "/spreadsheet/enrich",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=SpreadsheetJobResponse,
    summary="Enriquece planilha de itens (NCM + ICMS) de forma assíncrona",
)
async def enrich(
    request: Request,
    file: Annotated[UploadFile, File(description="Planilha .xlsx com colunas Descrição/NCM/UF")],
    uf_origem: Annotated[str, Query()] = "SP",
) -> SpreadsheetJobResponse:
    tenant_id = _get_tenant(request)
    if uf_origem.upper() not in UF.__members__:
        raise HTTPException(status_code=400, detail="UF de origem inválida.")

    from services.fiscal.spreadsheet.reader import load_items_from_bytes

    content = await file.read()
    # Validação/contagem síncrona (feedback 400/413) — não trafega as linhas.
    try:
        _colmap, rows = load_items_from_bytes(content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Planilha inválida: {exc}") from exc

    if len(rows) > _MAX_UPLOAD_ROWS:
        raise HTTPException(status_code=413, detail=f"Planilha excede o limite de {_MAX_UPLOAD_ROWS} linhas.")

    job_id = f"fiscal_{uuid.uuid4().hex[:16]}"

    # Grava o arquivo no MinIO e passa só a KEY ao worker (evita payload enorme no
    # Celery/Redis com as linhas inline — plano §3). O worker relê do MinIO.
    spreadsheet_key = f"fiscal/uploads/{tenant_id}/{job_id}.xlsx"
    try:
        from services.fiscal.storage import upload_spreadsheet
        upload_spreadsheet(spreadsheet_key, content)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Storage indisponível: {exc}") from exc

    try:
        from services.shared.redis_client import get_redis
        create_job = _lazy_create_job()
        create_job(get_redis(), job_id, len(rows), tenant_id)
    except Exception:
        pass  # Redis indisponível — job segue via Celery; polling degradado.

    try:
        _enqueue_enrich(job_id, tenant_id, spreadsheet_key, uf_origem.upper())
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Fila indisponível: {exc}") from exc

    return SpreadsheetJobResponse(
        job_id=job_id,
        status_url=f"/api/v1/fiscal/jobs/{job_id}",
        submitted_at=datetime.now(UTC).isoformat(),
    )


def _lazy_create_job():
    from services.scoring.idempotency import create_batch_job

    def _create(redis, job_id, total, tenant_id):
        # Reaproveita o rastreador de jobs em Redis do scoring (mesmo formato).
        create_batch_job(redis, [None] * total, tenant_id)
    return _create


def _enqueue_enrich(job_id: str, tenant_id: str, spreadsheet_key: str, uf_origem: str) -> None:
    """Despacho da task de enriquecimento (isolado p/ ser mockável nos testes de API)."""
    from celery import current_app as celery_app

    celery_app.send_task(
        "fiscal.tasks.enrich_spreadsheet",
        args=[job_id, tenant_id, spreadsheet_key, uf_origem],
        queue="fiscal",
    )


@router.get("/jobs/{job_id}", summary="Status do job de enriquecimento")
async def job_status(job_id: str, request: Request) -> dict[str, Any]:
    _get_tenant(request)
    try:
        from services.scoring.idempotency import get_batch_status
        from services.shared.redis_client import get_redis
        result = get_batch_status(get_redis(), job_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Redis indisponível: {exc}") from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} não encontrado (expira em 24h).")
    return result


@router.get("/audit/{request_id}", summary="Prova Merkle de uma triagem/lote")
async def audit(request_id: str, request: Request) -> dict[str, Any]:
    tenant_id = _get_tenant(request)
    try:
        proof = _get_ledger(tenant_id).get_proof(request_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": request_id, "proof": proof}
