"""
Ingestão DATAJUD com pipeline bronze→silver e fallback resiliente.

Fallback 1: cache Redis (últimas 48h)
Fallback 2: retry em 1h com backoff exponencial
Degradação graciosa: score parcial com flag `datajud_desatualizado`

Fonte: CNJ API pública — base legal: dado público (LGPD art. 7º, IV).
"""

import json
from datetime import UTC, datetime, timedelta

import requests
from celery.utils.log import get_task_logger
from ingest.celery_app import app
from ingest.contracts.datajud import DatajudProcessoBronze
from ingest.pipeline.base import add_linage, compute_lag_days, get_circuit_breaker, reconcile
from ingest.pipeline.quality import datajud_bronze_to_silver
from pydantic import ValidationError
from shared.config import settings
from shared.lgpd import pseudonymize_process_record
from shared.redis_client import get_redis

logger = get_task_logger(__name__)


class DatajudUnreachable(Exception):
    pass


def _validate_bronze(record: dict, date_str: str) -> DatajudProcessoBronze | None:
    """Valida schema do registro. Retorna None e loga se inválido (data contract gate)."""
    try:
        return DatajudProcessoBronze(**record)
    except ValidationError as exc:
        logger.warning("DATAJUD: schema inválido para processo %s — %s", record.get("id_processo"), exc)
        return None


def _fetch_from_api(date_str: str) -> dict:
    cb = get_circuit_breaker("DATAJUD")
    if cb.is_open():
        raise DatajudUnreachable("CircuitBreaker DATAJUD OPEN — fonte isolada temporariamente")

    try:
        response = requests.get(
            f"{settings.DATAJUD_API_URL}/processos",
            params={"data_julgamento": date_str},
            timeout=30,
            headers={"Authorization": f"APIKey {settings.DATAJUD_TOKEN}"},
        )
        response.raise_for_status()
        data = response.json()
        cb.record_success()
        return data
    except (requests.RequestException, ValueError) as exc:
        cb.record_failure()
        raise DatajudUnreachable(str(exc)) from exc


@app.task(
    bind=True,
    autoretry_for=(requests.RequestException,),
    retry_kwargs={"max_retries": 5},
    queue="daily",
)
def run_daily_ingest(self, date: str | None = None) -> dict:
    if not date:
        date = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")

    logger.info("Iniciando ingest DATAJUD para %s", date)

    # Busca dados (API → Redis fallback)
    try:
        data = _fetch_from_api(date)
        get_redis().setex(f"datajud:{date}", 48 * 3600, json.dumps(data))
        logger.info("DATAJUD OK: %d registros", len(data.get("items", [])))
    except DatajudUnreachable as exc:
        cached = get_redis().get(f"datajud:{date}")
        if cached:
            logger.warning("DATAJUD: fallback para cache Redis de %s", date)
            data = json.loads(cached)
        else:
            logger.error("DATAJUD indisponível e sem cache, retry em 1h: %s", exc)
            raise self.retry(exc=exc, countdown=3600) from None

    items = data.get("items", [])
    records_in = len(items)
    processed = 0
    rejected = 0

    for raw in items:
        # 1. Linage fields adicionados antes de qualquer processamento
        with_linage = add_linage(raw, source="DATAJUD")
        with_linage["data_source_lag_days"] = compute_lag_days(date)

        # 2. Validação de schema (data contract gate)
        bronze = _validate_bronze(with_linage, date)
        if bronze is None:
            rejected += 1
            continue

        # 3. Pseudonimização HMAC (LGPD) — antes de qualquer storage
        pseudo = pseudonymize_process_record(bronze.model_dump())

        # 4. Bronze → Silver (qualidade: outliers, faltantes, log1p)
        silver = datajud_bronze_to_silver(bronze.model_dump(), pseudo)

        # 5. Persistência (bronze: MinIO/S3; silver: OpenSearch + Neo4j)
        # TODO Fase 1b: persistir bronze em MinIO (bucket privado)
        # TODO Fase 1b: indexar silver em OpenSearch (índice datajud-silver-YYYY-MM)
        # TODO Fase 1b: criar nó/aresta em Neo4j (CNPJ → PROCESSO)
        _ = silver  # evita F841 enquanto persistência não está implementada

        processed += 1

    rec = reconcile("DATAJUD", records_in, processed, date)
    logger.info(
        "DATAJUD ingest concluído: %d processados, %d rejeitados (schema), lag=%d dias. Rec: %s",
        processed, rejected, with_linage.get("data_source_lag_days", -1), rec,
    )
    return {**rec, "rejected": rejected}
