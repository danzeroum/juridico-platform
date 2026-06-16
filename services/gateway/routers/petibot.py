"""
PetiBot — montagem de petição jurídica.

Endpoints:
  POST /api/v1/petibot/assemble
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.petibot.assembler import assemble_petition
from services.shared.contracts.petibot import PetiRequest

logger = logging.getLogger(__name__)
router = APIRouter()

# OTel — graceful degradation
try:
    from opentelemetry import trace as otel_trace
    _tracer = otel_trace.get_tracer("petibot")
    _OTEL = True
except ImportError:
    _OTEL = False
    _tracer = None  # type: ignore[assignment]


@router.post(
    "/petibot/assemble",
    summary="Monta estrutura de petição jurídica",
    responses={
        200: {
            "description": "Petição estruturada com seções padrão e precedentes",
            "content": {
                "application/json": {
                    "example": {
                        "tipo_acao": "TRABALHISTA",
                        "secoes": [
                            {"titulo": "Dos Fatos", "conteudo": "...", "ordem": 1},
                            {"titulo": "Do Direito", "conteudo": "...", "ordem": 2},
                            {"titulo": "Do Pedido", "conteudo": "...", "ordem": 3},
                        ],
                        "precedentes_encontrados": 3,
                        "contract_version": "petibot/v1",
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
                        "detail": "body → tipo_acao: Input should be 'TRABALHISTA', 'CIVEL', ...",
                        "instance": "/api/v1/petibot/assemble",
                        "contract_version": "1.0",
                    }
                }
            },
        },
    },
)
async def assemble(case: PetiRequest) -> JSONResponse:
    """
    Monta estrutura de petição com seções padrão e precedentes via RAG.

    Fase 4: retorna template (sem geração LLM).
    Precedentes via ChromaDB; degradação graciosa se offline.
    """
    ctx_manager = _tracer.start_as_current_span("petibot.assemble") if _OTEL else _noop_span()
    with ctx_manager as span:
        if _OTEL and span:
            span.set_attribute("tipo_acao", case.tipo_acao.value)
        response = assemble_petition(case)
        return JSONResponse(content=response.model_dump(), status_code=200)


class _noop_span:
    def __enter__(self): return None
    def __exit__(self, *_): pass
