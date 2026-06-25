"""
LicitaWatch — monitoramento de licitações públicas (PNCP).

Endpoints:
  GET  /api/v1/licitawatch/contratos/{cnpj_orgao}   — lista contratos (Redis cache)
  POST /api/v1/licitawatch/orgao/{cnpj_orgao}/evaluate — avalia regras LL01–LL04
"""
from __future__ import annotations

import json
import logging
import os

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from services.gateway.observability import span as obs_span
from services.ingest.contracts.pncp import PncpContratoSilver
from services.licitawatch.monitor import build_indicadores_from_silver, evaluate_licitacoes

logger = logging.getLogger(__name__)
router = APIRouter()

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def _get_redis():
    import redis as redis_lib
    return redis_lib.from_url(_REDIS_URL, decode_responses=True)


@router.get("/contratos/{cnpj_orgao}")
async def list_contratos(
    cnpj_orgao: str,
    referencia: str = Query(..., description="Ano de referência (YYYY)"),
) -> JSONResponse:
    """Lista contratos PNCP do órgão a partir do cache Redis."""
    if not cnpj_orgao.isdigit() or len(cnpj_orgao) != 14:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "https://juridico.io/errors/licitawatch/cnpj-invalido",
                "title": "CNPJ inválido",
                "status": 422,
                "detail": "cnpj_orgao deve ter 14 dígitos numéricos",
                "instance": f"/api/v1/licitawatch/contratos/{cnpj_orgao}",
                "contract_version": "licitawatch/v1",
            },
        )
    with obs_span("licitawatch.list_contratos", {"cnpj_orgao": cnpj_orgao[:6] + "****", "referencia": referencia}):
        try:
            r = _get_redis()
            pattern = f"pncp:{cnpj_orgao}:{referencia}:*"
            keys = list(r.scan_iter(pattern, count=100))
            contratos = []
            for k in keys[:200]:
                raw = r.get(k)
                if raw:
                    contratos.append(json.loads(raw))
            return JSONResponse({"cnpj_orgao": cnpj_orgao, "referencia": referencia, "contratos": contratos, "total": len(contratos)})
        except Exception as exc:
            logger.warning("Redis indisponível para LicitaWatch: %s", exc)
            return JSONResponse({"cnpj_orgao": cnpj_orgao, "referencia": referencia, "contratos": [], "total": 0})


@router.post("/orgao/{cnpj_orgao}/evaluate")
async def evaluate_orgao(
    cnpj_orgao: str,
    referencia: str = Query(..., description="Ano de referência (YYYY)"),
) -> JSONResponse:
    """Avalia regras LL01–LL04 para o órgão e retorna AlertEnvelopes."""
    if not cnpj_orgao.isdigit() or len(cnpj_orgao) != 14:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "https://juridico.io/errors/licitawatch/cnpj-invalido",
                "title": "CNPJ inválido",
                "status": 422,
                "detail": "cnpj_orgao deve ter 14 dígitos numéricos",
                "instance": f"/api/v1/licitawatch/orgao/{cnpj_orgao}/evaluate",
                "contract_version": "licitawatch/v1",
            },
        )
    try:
        r = _get_redis()
        pattern = f"pncp:{cnpj_orgao}:{referencia}:*"
        keys = list(r.scan_iter(pattern, count=100))
        contratos: list[PncpContratoSilver] = []
        for k in keys[:500]:
            raw = r.get(k)
            if raw:
                try:
                    contratos.append(PncpContratoSilver(**json.loads(raw)))
                except Exception:
                    pass
    except Exception:
        contratos = []

    with obs_span("licitawatch.evaluate_orgao", {"cnpj_orgao": cnpj_orgao[:6] + "****", "referencia": referencia}):
        ind = build_indicadores_from_silver(cnpj_orgao, referencia, contratos)
        envelopes = evaluate_licitacoes(ind)

        return JSONResponse({
            "cnpj_orgao": cnpj_orgao,
            "referencia": referencia,
            "total_contratos": ind.total_contratos,
            "indicadores": {
                "pct_mesmo_vencedor": ind.pct_mesmo_vencedor,
                "pct_dispensa": ind.pct_dispensa,
                "pct_unico_proponente": ind.pct_unico_proponente,
                "pct_prazo_curto": ind.pct_prazo_curto,
            },
            "alertas": len(envelopes),
            "envelopes": [e.model_dump(mode="json") for e in envelopes],
            "contract_version": "licitawatch/v1",
        })


