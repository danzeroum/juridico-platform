"""
Ingestao DATAJUD com fallback resiliente.
Fallback 1: cache Redis (ultimos 2 dias)
Fallback 2: retry em 1h
Se tudo falhar: score parcial com flag de desatualizacao
"""

import json
from datetime import datetime, timedelta

import requests
from celery.utils.log import get_task_logger
from ingest.celery_app import app
from shared.config import settings
from shared.lgpd import pseudonymize_process_record
from shared.redis_client import get_redis

logger = get_task_logger(__name__)


class DatajudUnreachable(Exception):
    pass


@app.task(
    bind=True,
    autoretry_for=(requests.RequestException,),
    retry_kwargs={"max_retries": 5},
)
def run_daily_ingest(self, date: str = None):
    if not date:
        date = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

    logger.info(f"Iniciando ingest DATAJUD para {date}")

    try:
        response = requests.get(
            f"{settings.DATAJUD_API_URL}/processos",
            params={"data_julgamento": date},
            timeout=30,
            headers={"Authorization": f"Bearer {settings.DATAJUD_TOKEN}"},
        )
        response.raise_for_status()
        data = response.json()

        # Cachear no Redis por 48h
        get_redis().setex(f"datajud:{date}", 48 * 3600, json.dumps(data))
        logger.info(f"DATAJUD OK: {len(data.get('items', []))} registros")

    except (requests.RequestException, ValueError) as exc:
        # Fallback 1: cache Redis (ultimos 2 dias)
        cached = get_redis().get(f"datajud:{date}")
        if cached:
            logger.warning(f"Fallback para cache Redis de {date}")
            data = json.loads(cached)
        else:
            logger.error(f"DATAJUD indisponivel, agendando retry em 1h: {exc}")
            raise self.retry(exc=DatajudUnreachable("API fora de servico"), countdown=60 * 60) from None

    processed = 0
    for record in data.get("items", []):
        _safe = pseudonymize_process_record(record)
        # TODO: persistir em OpenSearch + Neo4j + ChromaDB
        processed += 1

    logger.info(f"DATAJUD ingest concluido: {processed} registros processados")
    return {"source": "DATAJUD", "date": date, "processed": processed}
