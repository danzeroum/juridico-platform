"""
Celery Beat — Recalibração periódica do modelo TaxPredict.

IMPORTANTE: fit() executa MCMC (minutos). Nunca chamar por request.
Agendar para fora do horário de pico (ex.: 02:00 BRT, sábados).

Beatschedule de exemplo:
    app.conf.beat_schedule = {
        "taxpredict-recalibrate-pis-cofins": {
            "task": "taxpredict.recalibrate",
            "schedule": crontab(day_of_week="saturday", hour=2, minute=0),
            "args": ["PIS_COFINS"],
        },
    }
"""
from __future__ import annotations

import io
import logging
import os

from services.taxpredict.celery_app import app

logger = logging.getLogger(__name__)

_MINIO_BUCKET = os.getenv("TAXPREDICT_BUCKET", "gold")


@app.task(bind=True, queue="taxpredict", name="taxpredict.recalibrate")
def recalibrate_model(self, materia: str = "PIS_COFINS") -> dict:
    """
    Recalibra o modelo Bayesiano com novos dados de desfecho.

    1. Carrega DataFrame de treino do MinIO (gold/taxpredict/training/{materia}.parquet)
    2. Chama model.fit() — MCMC roda aqui, nunca no path da request
    3. Persiste o trace de volta no MinIO
    """
    try:
        import pandas as pd
        from minio import Minio

        from services.shared.config import settings
        from services.taxpredict.model.bayesian import TaxPredictionModel

        minio = Minio(
            settings.MINIO_URL.replace("http://", "").replace("https://", ""),
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_URL.startswith("https://"),
        )

        data_key = f"taxpredict/training/{materia.lower().replace('/', '_')}.parquet"
        model_key = f"taxpredict/{materia.lower().replace('/', '_')}.nc"

        data_obj = minio.get_object(_MINIO_BUCKET, data_key)
        df = pd.read_parquet(io.BytesIO(data_obj.read()))

        logger.info("Recalibrando TaxPredict matéria=%s n=%d", materia, len(df))
        model = TaxPredictionModel(materia)
        model.fit(df)
        model.save_to_minio(minio, _MINIO_BUCKET, model_key)
        logger.info("Recalibração concluída matéria=%s", materia)
        return {"status": "ok", "materia": materia, "n_samples": len(df)}

    except Exception as exc:
        logger.error("Falha na recalibração matéria=%s: %s", materia, exc)
        raise self.retry(exc=exc, countdown=300, max_retries=3) from exc
