"""
Defensor — agente jurídico de IA (pipeline agêntico + timeline de eventos).

Endpoints:
  POST /api/v1/defensor/run
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.defensor.orchestrator import run_agente
from services.shared.contracts.defensor import DEFENSOR_CONTRACT_VERSION, DefensorRequest

logger = logging.getLogger(__name__)
router = APIRouter()

# OTel — graceful degradation
try:
    from opentelemetry import trace as otel_trace
    _tracer = otel_trace.get_tracer("defensor")
    _OTEL = True
except ImportError:
    _OTEL = False
    _tracer = None  # type: ignore[assignment]


@router.post(
    "/run",
    summary="Roda o agente Defensor sobre um caso",
    responses={
        200: {
            "description": "Timeline de eventos do agente + defesa montada e handoff",
            "content": {
                "application/json": {
                    "example": {
                        "classificacao": "CONSUMERISTA · PROCON",
                        "canal": "PROCON",
                        "eventos": [
                            {"ts": "12:48:04", "evento": "caso.classificado", "detalhe": "cobrança indevida", "status": "ok"},
                            {"ts": "12:48:06", "evento": "subsidios.ok", "detalhe": "3 docs anexados", "status": "ok"},
                            {"ts": "12:48:12", "evento": "jurisprudencia.match", "detalhe": "47 precedentes", "status": "ok"},
                            {"ts": "12:48:14", "evento": "defesa.pronta", "detalhe": "4 seções", "status": "ok"},
                        ],
                        "precedentes_encontrados": 3,
                        "casos_anteriores": 3,
                        "subsidios": ["contrato/termo de adesão", "histórico de cobranças"],
                        "proximo_responsavel": "agente",
                        "status": "DEFESA_PRONTA",
                        "contract_version": "defensor/v1",
                    }
                }
            },
        },
        422: {
            "description": "Dados de entrada inválidos",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://juridico-platform/errors/validation-error",
                        "title": "Erro de validação",
                        "status": 422,
                        "detail": "body → canal: Input should be 'PROCON', 'CONSUMIDOR_GOV', ...",
                        "instance": "/api/v1/defensor/run",
                        "contract_version": "1.0",
                    }
                }
            },
        },
    },
)
async def run(case: DefensorRequest) -> JSONResponse:
    """
    Executa o pipeline agêntico (classificar → consultar → subsídios → jurisprudência →
    redigir → preparar protocolo) e devolve a timeline + a defesa montada.

    Etapas determinísticas; jurisprudência via RAG (degradação graciosa se offline).
    """
    ctx_manager = _tracer.start_as_current_span("defensor.run") if _OTEL else _noop_span()
    with ctx_manager as span:
        if _OTEL and span:
            span.set_attribute("canal", case.canal.value)
            span.set_attribute("tipo_caso", case.tipo_caso.value)
        response = run_agente(case)
        return JSONResponse(content=response.model_dump(), status_code=200)


@router.get(
    "/reputacao/{termo:path}",  # :path tolera barras no nome da empresa
    summary="Reputação da empresa no Consumidor.gov (dados abertos)",
)
async def reputacao(termo: str) -> JSONResponse:
    """
    Indicadores de reputação da empresa reclamada agregados do Consumidor.gov
    (total de reclamações, % resposta, % resolução, nota média).

    Lê o cache populado pelo ingest (`make ingest-consumidor`). Retorna
    encontrado=false enquanto não houver dados (degradação graciosa).
    """
    import json
    import os

    from services.ingest.tasks.consumidor_gov import slugify

    slug = slugify(termo)
    raw = None
    try:
        import redis as redis_lib

        r = redis_lib.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True
        )
        raw = r.get(f"consumidor:{slug}")
    except Exception as exc:
        logger.debug("Redis indisponível para reputação Defensor: %s", exc)

    data = json.loads(raw) if raw else {}
    return JSONResponse(content={
        "termo": termo,
        "encontrado": bool(data),
        "reputacao": data,
        "source": "Consumidor.gov",
        "contract_version": DEFENSOR_CONTRACT_VERSION,
    })


class _noop_span:
    def __enter__(self): return None
    def __exit__(self, *_): pass
