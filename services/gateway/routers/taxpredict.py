"""
TaxPredict — Previsão probabilística de desfecho tributário.

Endpoints:
  POST /api/v1/taxpredict/predict

SLA: p95 < 3s. MCMC nunca roda neste path.
Fallback: prior nacional (is_fallback=True) quando trace não carregado.
Recalibração: serviço Celery Beat (taxpredict.recalibrate).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from services.shared.contracts.taxpredict import (
    PRIOR_CI_LOWER,
    PRIOR_CI_UPPER,
    PRIOR_NACIONAL,
    TAXPREDICT_CONTRACT_VERSION,
    Decisao,
    JurisprudenciaHit,
    TaxPredictRequest,
    TaxPredictResponse,
    extract_features,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Trace carregado uma vez no startup (lazy on first request); thread-safe reads.
_MODEL_CACHE: dict[str, Any] = {}
_RAG_N_RESULTS = 5


def _get_model(materia: str) -> Any | None:
    """
    Lazy-load do trace Bayesiano do MinIO.
    Retorna None se indisponível — ativa o fallback com prior nacional.
    """
    if materia in _MODEL_CACHE:
        return _MODEL_CACHE[materia]
    try:
        from minio import Minio

        from services.shared.config import settings
        from services.taxpredict.model.bayesian import TaxPredictionModel

        minio = Minio(
            settings.MINIO_URL.replace("http://", "").replace("https://", ""),
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_URL.startswith("https://"),
        )
        model = TaxPredictionModel(materia)
        model_key = f"taxpredict/{materia.lower().replace('/', '_')}.nc"
        model.load_from_minio(minio, "gold", model_key)
        _MODEL_CACHE[materia] = model
        return model
    except Exception as exc:
        logger.warning("Trace TaxPredict indisponível matéria=%s: %s", materia, exc)
        return None


def _rag_lookup(descricao: str, materia: str) -> list[JurisprudenciaHit]:
    """
    Busca jurisprudências similares no ChromaDB.
    Retorna lista vazia se ChromaDB/Ollama indisponível (degradação graciosa).
    """
    try:
        from services.shared.ai.rag import RAGEngine

        rag = RAGEngine(collection_name="taxpredict_jurisprudencia")
        results = rag.search(query=descricao, n_results=_RAG_N_RESULTS)
        hits: list[JurisprudenciaHit] = []
        for r in results:
            meta = r.get("metadata") or {}
            distance = r.get("distance") or 1.0
            similarity = round(max(0.0, min(1.0, 1.0 - float(distance))), 4)
            decisao_raw = str(meta.get("decisao", "DESCONHECIDO")).upper()
            try:
                decisao = Decisao(decisao_raw)
            except ValueError:
                decisao = Decisao.DESCONHECIDO
            ano_raw = meta.get("ano")
            hits.append(
                JurisprudenciaHit(
                    doc_id=str(r["id"]),
                    similarity=similarity,
                    ementa=str(r.get("document", ""))[:500],
                    decisao=decisao,
                    tribunal=meta.get("tribunal"),
                    ano=int(ano_raw) if ano_raw else None,
                )
            )
        return hits
    except Exception as exc:
        logger.warning("RAG lookup falhou: %s", exc)
        return []


@router.post("/taxpredict/predict")
async def predict(case: TaxPredictRequest, request: Request) -> JSONResponse:
    """
    Predição probabilística de desfecho tributário.

    Retorna probabilidade de êxito (P(favorável)), intervalo de credibilidade 95%,
    features usadas e jurisprudências similares recuperadas via RAG.

    Quando o trace não está carregado, retorna o prior nacional
    (probability=0.30, is_fallback=True) sem erro — o cliente pode exibir
    a estimativa com aviso de que o modelo está em recalibração.
    """
    materia = case.materia.value
    features = extract_features(case)

    jurisprudencias = _rag_lookup(case.descricao, materia)

    model = _get_model(materia)
    is_fallback = model is None or not getattr(model, "is_ready", False)

    if is_fallback:
        prob = PRIOR_NACIONAL
        ci_lower = PRIOR_CI_LOWER
        ci_upper = PRIOR_CI_UPPER
        model_version = "prior_nacional_v1"
    else:
        try:
            result = model.predict(features)
            prob = result["probability"]
            ci_lower = result["ci_lower"]
            ci_upper = result["ci_upper"]
            model_version = f"bayesian_hierarquico_{materia}_v1"
        except Exception as exc:
            logger.error("Predição falhou matéria=%s: %s", materia, exc)
            raise HTTPException(
                status_code=503,
                detail={
                    "type": "https://juridico.io/errors/taxpredict/model-unavailable",
                    "title": "Model Unavailable",
                    "status": 503,
                    "detail": f"Falha na predição para matéria {materia}. Tente novamente.",
                    "instance": str(request.url),
                    "contract_version": TAXPREDICT_CONTRACT_VERSION,
                },
            ) from exc

    response = TaxPredictResponse(
        materia=materia,
        probability=round(prob, 4),
        ci_lower=round(ci_lower, 4),
        ci_upper=round(ci_upper, 4),
        rag_hits=len(jurisprudencias),
        jurisprudencias=jurisprudencias,
        features_used=features,
        computed_at=datetime.now(UTC).isoformat(),
        model_version=model_version,
        is_fallback=is_fallback,
    )
    return JSONResponse(content=response.model_dump(), status_code=200)
