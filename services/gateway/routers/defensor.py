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
from services.defensor.protocolar import protocolar
from services.gateway.observability import span as obs_span
from services.shared.contracts.defensor import DEFENSOR_CONTRACT_VERSION, DefensorRequest
from services.shared.contracts.protocolo import ProtocoloRequest

logger = logging.getLogger(__name__)
router = APIRouter()


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
    with obs_span("defensor.run", {"canal": case.canal.value, "tipo_caso": case.tipo_caso.value}):
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


@router.post(
    "/protocolar",
    summary="Protocola a defesa no órgão (simulação por padrão)",
    responses={
        200: {
            "description": "Resultado do protocolo. Em modo simulação (padrão), status=SIMULADO.",
            "content": {
                "application/json": {
                    "example": {
                        "canal": "PROCON",
                        "modo": "simulacao",
                        "status": "SIMULADO",
                        "numero_protocolo": "SIM-PROCON-1A2B3C4D5E",
                        "url": None,
                        "mensagem": "Protocolo SIMULADO — nenhuma submissão real foi feita.",
                        "contract_version": "protocolo/v1",
                    }
                }
            },
        },
        422: {"description": "Dados de entrada inválidos"},
    },
)
async def protocolar_endpoint(req: ProtocoloRequest) -> JSONResponse:
    """
    Protocola (ou simula) a defesa no canal informado.

    Por padrão roda em SIMULAÇÃO — nenhuma submissão real é feita. A submissão
    real exige PROTOCOLO_MODO=real, credenciais do portal e host liberado na
    allowlist de rede (ver docs/PROTOCOLO-AUTOMACAO.md).
    """
    with obs_span("defensor.protocolar", {"canal": req.canal.value}):
        resultado = protocolar(req)
        return JSONResponse(content=resultado.model_dump(), status_code=200)
