"""
Tarefas Celery para LegalScore.

run_batch_score: score de até 1.000 CNPJs em paralelo de thread-pool.
SLA: 1k CNPJs < 30s (cada CNPJ usa cache Redis — sem I/O de banco).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import Any

from services.scoring.celery_app import app
from services.scoring.features import assemble_features
from services.scoring.idempotency import update_batch_progress
from services.shared.contracts.scoring import ScoreRequest as EngineScoreRequest
from services.shared.redis_client import get_redis

logger = logging.getLogger(__name__)

_MAX_WORKERS = 20  # thread-pool: I/O-bound (Redis gets)


def _score_single(cnpj: str, redis: Any) -> dict:
    """Score de um único CNPJ. Chamado em thread-pool."""
    from services.scoring.engine.factory import get_score_engine

    try:
        fv = assemble_features(cnpj, redis)
        engine = get_score_engine()
        req = EngineScoreRequest(cnpj=cnpj, features=fv.features, cnae_2dig=fv.cnae_2dig)
        result = engine.score(req)
        return {
            "cnpj": cnpj,
            "score": result.score,
            "risk_level": result.risk_level,
            "confidence_interval": list(result.confidence_interval),
            "breakdown": result.breakdown,
            "is_partial": fv.is_partial,
            "sources_missing": fv.sources_missing,
            "source_date": fv.source_date,
            "engine": result.engine,
            "error": None,
        }
    except Exception as exc:
        logger.warning("Erro ao calcular score para %s: %s", cnpj, exc)
        return {"cnpj": cnpj, "score": None, "risk_level": None, "error": str(exc)}


@app.task(bind=True, queue="scoring")
def run_batch_score(self, job_id: str, cnpjs: list[str]) -> dict:
    """
    Calcula score para lista de CNPJs em paralelo (thread-pool).

    Resultado armazenado em Redis com chave batch:{job_id}.
    SLA: 1k CNPJs < 30s quando o cache Redis tem os dados de PGFN/Receita.
    """
    redis = get_redis()
    results: list[dict] = []
    processed = 0

    update_batch_progress(redis, job_id, 0, [], status="processing")

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {pool.submit(_score_single, cnpj, redis): cnpj for cnpj in cnpjs}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            processed += 1
            # Atualiza progresso a cada 100 CNPJs
            if processed % 100 == 0:
                update_batch_progress(redis, job_id, processed, results, status="processing")

    completed_at = datetime.now(UTC).isoformat()
    update_batch_progress(redis, job_id, processed, results, status="done", completed_at=completed_at)

    logger.info("Batch %s concluído: %d/%d CNPJs", job_id, processed, len(cnpjs))
    return {"job_id": job_id, "processed": processed, "total": len(cnpjs)}
