"""
Ingestão PGFN (Dívida Ativa da União) — cadência semanal.

Consulta situação fiscal por CNPJ na API pública do PGFN.
Dados de dívida não contêm PII individual (CNPJ de PJ é público).

Base legal: obrigação legal (LGPD art. 7º, II) + dado público.
"""

import json
from datetime import UTC, datetime
from typing import Any

import requests
from celery.utils.log import get_task_logger
from pydantic import ValidationError

from services.ingest.celery_app import app
from services.ingest.contracts.pgfn import PgfnDevedorBronze
from services.ingest.pipeline.base import add_linage, get_circuit_breaker, reconcile
from services.ingest.pipeline.quality import pgfn_bronze_to_silver
from services.shared.config import settings
from services.shared.redis_client import get_redis

logger = get_task_logger(__name__)

_CACHE_TTL = 7 * 24 * 3600  # 7 dias (cadência semanal)


def _fetch_pgfn_cnpj(cnpj: str) -> dict[str, Any]:
    """Consulta situação fiscal de um CNPJ no PGFN."""
    cb = get_circuit_breaker("PGFN")
    if cb.is_open():
        raise requests.RequestException("CircuitBreaker PGFN OPEN")

    try:
        resp = requests.get(
            f"{settings.PGFN_API_URL}/situacao/{cnpj}",
            timeout=30,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        cb.record_success()
        return resp.json()
    except (requests.RequestException, ValueError):
        cb.record_failure()
        raise


def _validate_bronze(record: dict) -> PgfnDevedorBronze | None:
    try:
        return PgfnDevedorBronze(**record)
    except ValidationError as exc:
        logger.warning("PGFN: schema inválido para CNPJ %s — %s", record.get("cnpj"), exc)
        return None


@app.task(bind=True, queue="weekly")
def run_weekly_ingest(self, cnpjs: list[str] | None = None) -> dict:
    """
    Ingere situação fiscal de uma lista de CNPJs do PGFN.

    Se `cnpjs` for None, opera no modo batch padrão (a ser configurado
    com a lista de CNPJs monitorados no banco na Fase 1c).
    """
    if not cnpjs:
        logger.info("PGFN: lista de CNPJs vazia — aguardando Fase 1c (gateway + batch)")
        return {"source": "PGFN", "status": "no_cnpjs", "processed": 0}

    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    redis = get_redis()
    records_in = len(cnpjs)
    processed = 0
    rejected = 0

    for cnpj in cnpjs:
        cache_key = f"pgfn:{cnpj}"
        cached = redis.get(cache_key)

        if cached:
            raw = json.loads(cached)
        else:
            try:
                raw = _fetch_pgfn_cnpj(cnpj)
                redis.setex(cache_key, _CACHE_TTL, json.dumps(raw))
            except requests.RequestException as exc:
                logger.warning("PGFN: falha ao consultar %s — %s", cnpj, exc)
                continue

        raw = add_linage(raw, source="PGFN")

        bronze = _validate_bronze(raw)
        if bronze is None:
            rejected += 1
            continue

        silver = pgfn_bronze_to_silver(bronze.model_dump())

        # TODO Fase 1b: persistir silver em OpenSearch (índice pgfn-silver-YYYY-MM)
        # TODO Fase 1b: atualizar nó CNPJ no Neo4j com flag tem_divida_ativa
        _ = silver

        processed += 1

    rec = reconcile("PGFN", records_in, processed, date_str)
    logger.info("PGFN ingest concluído: %s", rec)
    return {**rec, "rejected": rejected}


@app.task(bind=True, queue="weekly")
def run_weekly_ingest_single(self, cnpj: str) -> dict:
    """Ingere um único CNPJ — usada pelo gateway (Fase 1c) para consultas on-demand."""
    return run_weekly_ingest(cnpjs=[cnpj])
