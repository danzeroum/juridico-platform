"""
ConciliaIA — recomendação de faixa de acordo.

Endpoints:
  POST /api/v1/concilia/recommend
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.concilia.recommender import recommend_settlement
from services.gateway.observability import span as obs_span
from services.shared.contracts.concilia import ConciliaRequest

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_taxpredict(descricao: str, materia: str) -> float | None:
    """Probabilidade TaxPredict (degradação graciosa se offline)."""
    try:
        # Reusa cache do router taxpredict via import lazy
        from services.gateway.routers.taxpredict import _get_model
        from services.shared.contracts.taxpredict import (
            Materia,
            TaxPredictRequest,
            extract_features,
        )
        from services.taxpredict.model.bayesian import TaxPredictionModel  # noqa: F401

        tax_req = TaxPredictRequest(descricao=descricao[:2000], materia=Materia(materia))
        features = extract_features(tax_req)
        model: Any = _get_model(materia)
        if model and getattr(model, "is_ready", False):
            result = model.predict(features)
            return result.get("probability")
    except Exception as exc:
        logger.debug("TaxPredict indisponível para ConciliaIA: %s", exc)
    return None


def _get_legalscore(cnpj: str | None) -> int | None:
    """LegalScore do réu (degradação graciosa se Redis/modelo offline)."""
    if not cnpj:
        return None
    try:
        import json

        from services.shared.redis_client import get_redis
        redis = get_redis()
        key = f"score:{cnpj}"
        raw = redis.get(key)
        if raw:
            data = json.loads(raw)
            return data.get("score")
    except Exception as exc:
        logger.debug("LegalScore indisponível para ConciliaIA: %s", exc)
    return None


@router.post(
    "/recommend",
    summary="Recomenda faixa de acordo",
    responses={
        200: {
            "description": "Recomendação de acordo com fatores e faixa de valor",
            "content": {
                "application/json": {
                    "example": {
                        "tipo_acao": "TRABALHISTA",
                        "valor_causa": 50000.0,
                        "faixa_min": 15000.0,
                        "faixa_max": 30000.0,
                        "percentual_min": 0.30,
                        "percentual_max": 0.60,
                        "fatores": [
                            {"nome": "probabilidade_favorable", "impacto": -0.05},
                            {"nome": "risco_reu", "impacto": 0.05},
                        ],
                        "contract_version": "concilia/v1",
                    }
                }
            },
        },
        422: {
            "description": "Dados inválidos",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://juridico-platform/errors/validation-error",
                        "title": "Erro de validação",
                        "status": 422,
                        "detail": "body → valor_causa: Input should be greater than 0",
                        "instance": "/api/v1/concilia/recommend",
                        "contract_version": "1.0",
                    }
                }
            },
        },
    },
)
async def recommend(case: ConciliaRequest) -> JSONResponse:
    """
    Recomenda faixa de acordo baseada em prior histórico,
    probabilidade TaxPredict e risco LegalScore do réu.

    Todos os enriquecimentos são opcionais: degradação graciosa se offline.
    """
    tipo = case.tipo_acao.value

    with obs_span("concilia.recommend", {"tipo_acao": tipo, "valor_causa": float(case.valor_causa)}):
        probability_favorable = _get_taxpredict(case.descricao, tipo)
        risk_score_reu = _get_legalscore(case.cnpj_reu)

        response = recommend_settlement(
            request=case,
            probability_favorable=probability_favorable,
            risk_score_reu=risk_score_reu,
        )
        return JSONResponse(content=response.model_dump(), status_code=200)
