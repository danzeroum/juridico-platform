"""
Knowledge Graph + Litigant Network — consultas ao grafo Empresa→Processo.

Read-only sobre Neo4j (populado pela ingestão DATAJUD). Só dados públicos
(CNPJ↔processo); pessoas naturais não são expostas (pseudonimizadas no ingest).
Segue o template P2 (JWT via _get_tenant, problem+json global, OTel opcional).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status

from services.knowledge_graph import queries

try:
    from opentelemetry import trace as otel_trace
    _tracer = otel_trace.get_tracer("knowledge_graph")
    _OTEL = True
except ImportError:
    _OTEL = False
    _tracer = None  # type: ignore[assignment]

router = APIRouter(tags=["knowledge-graph"])


def _get_tenant(request: Request) -> str:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token JWT não contém tenant_id.",
        )
    return tenant_id


@router.get("/stats", summary="Estatísticas globais do grafo")
async def stats(request: Request) -> Any:
    _get_tenant(request)
    return queries.graph_stats()


@router.get(
    "/company/{cnpj}/processes",
    summary="Processos ligados a uma empresa",
    responses={200: {"description": "Lista de processos (nós Processo)"}},
)
async def company_processes(
    cnpj: str, request: Request, limit: int = Query(default=100, ge=1, le=500)
) -> Any:
    _get_tenant(request)
    span = _tracer.start_as_current_span("kg.company_processes") if _OTEL else _noop_span()
    with span:
        rows = queries.company_processes(cnpj, limit)
    return {"cnpj": cnpj, "count": len(rows), "results": rows}


@router.get(
    "/company/{cnpj}/network",
    summary="Rede de co-litigância (empresas com processos em comum)",
    description=(
        "Retorna empresas que compartilham processos com o CNPJ informado, "
        "classificadas por intensidade (ISOLADO→PREDATORIO). Apenas CNPJ↔CNPJ "
        "(dados públicos)."
    ),
)
async def company_network(
    cnpj: str, request: Request, limit: int = Query(default=50, ge=1, le=200)
) -> Any:
    _get_tenant(request)
    span = _tracer.start_as_current_span("kg.litigant_network") if _OTEL else _noop_span()
    with span:
        return queries.litigant_network(cnpj, limit)


class _noop_span:
    def __enter__(self): return None
    def __exit__(self, *_): pass
