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
from pydantic import ValidationError

from services.ingest.celery_app import app
from services.ingest.contracts.datajud import DatajudProcessoBronze
from services.ingest.pipeline.base import (
    add_linage,
    compute_lag_days,
    get_circuit_breaker,
    persist_silver,
    reconcile,
)
from services.ingest.pipeline.quality import datajud_bronze_to_silver
from services.shared.config import settings
from services.shared.lgpd import pseudonymize_process_record
from services.shared.redis_client import get_redis
from services.shared.storage.neo4j_client import upsert_process_edges

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
    bronze_batch: list[dict] = []
    silver_batch: list[dict] = []

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

        # 4. Bronze → Silver (qualidade + normalização TPU de classe/assunto)
        silver = datajud_bronze_to_silver(bronze.model_dump(), pseudo)

        # 5. Acumula para persistência em batelada (bulk é 10-100x mais barato
        #    que por-registro em OpenSearch/Neo4j). O bronze gravado é o registro
        #    JÁ pseudonimizado — nunca PII em claro em nenhum store.
        bronze_batch.append(pseudo)
        silver_batch.append(silver)
        processed += 1

    # 6. Persistência durável (Fase 1b): bronze→MinIO, silver→OpenSearch, grafo→Neo4j.
    #    Degradação graciosa por store dentro de persist_silver.
    persist_result = persist_silver(
        source="DATAJUD",
        date_str=date,
        bronze_records=bronze_batch,
        silver_records=silver_batch,
        opensearch_index=f"datajud-silver-{date[:7]}",
        graph_writer=upsert_process_edges,
        id_field="id_processo",
    )

    rec = reconcile("DATAJUD", records_in, processed, date)
    logger.info(
        "DATAJUD ingest concluído: %d processados, %d rejeitados (schema), lag=%d dias. "
        "Persist: %s. Rec: %s",
        processed, rejected, with_linage.get("data_source_lag_days", -1), persist_result, rec,
    )
    return {**rec, "rejected": rejected, "persist": persist_result}
