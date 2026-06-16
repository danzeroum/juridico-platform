"""
Ingest task para SICONFI (Sistema de Informações Contábeis e Fiscais do Setor Público).

Cadência: mensal (Celery Beat).
Fonte: API STN (https://apidatalake.tesouro.gov.br/ords/siconfi/).
Cache Redis: chave siconfi:{cod_ibge}:{exercicio}, TTL 7 dias.
"""
from __future__ import annotations

import json
import logging

import requests
from celery.utils.log import get_task_logger
from ingest.celery_app import app
from pydantic import ValidationError
from services.ingest.contracts.siconfi import (
    SiconfiContaBronze,
    siconfi_bronze_to_silver,
)
from services.ingest.pipeline.base import get_circuit_breaker, reconcile
from services.shared.config import settings

logger = get_task_logger(__name__)

SICONFI_BASE_URL = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"
CACHE_TTL = 60 * 60 * 24 * 7  # 7 dias


def _cache_key(cod_ibge: str, exercicio: int) -> str:
    return f"siconfi:{cod_ibge}:{exercicio}"


def _fetch_siconfi_api(cod_ibge: str, exercicio: int) -> list[dict]:
    """Busca demonstrativos financeiros municipais via API STN."""
    cb = get_circuit_breaker("siconfi")
    if cb.is_open():
        logger.warning("CircuitBreaker SICONFI aberto — skip fetch")
        return []

    try:
        resp = requests.get(
            f"{SICONFI_BASE_URL}/rreo",
            params={"id_ente": cod_ibge, "an_exercicio": exercicio, "nr_periodo": 6},
            timeout=30,
        )
        resp.raise_for_status()
        cb.record_success()
        data = resp.json()
        return data.get("items", []) if isinstance(data, dict) else []
    except Exception as exc:
        cb.record_failure()
        logger.warning("Erro ao buscar SICONFI %s/%s: %s", cod_ibge, exercicio, exc)
        return []


def _validate_bronze(raw: dict) -> SiconfiContaBronze | None:
    try:
        return SiconfiContaBronze(**raw)
    except (ValidationError, TypeError) as exc:
        logging.warning("SICONFI bronze inválido: %s | %s", exc, raw)
        return None


@app.task(bind=True, max_retries=3, default_retry_delay=120)
def run_monthly_ingest(self, cod_ibge: str, exercicio: int) -> dict:
    """
    Ingest mensal SICONFI para um município.

    cod_ibge: código IBGE de 7 dígitos
    exercicio: ano (ex: 2024)
    """
    import redis as redis_lib

    r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
    cache_key = _cache_key(cod_ibge, exercicio)

    cached = r.get(cache_key)
    if cached:
        return {"source": "SICONFI", "status": "cached", "cod_ibge": cod_ibge}

    raw_list = _fetch_siconfi_api(cod_ibge, exercicio)
    records_in = len(raw_list)
    records_out = 0
    rejected = 0
    silver_list = []

    for raw in raw_list:
        raw["cod_ibge"] = raw.get("cod_ibge", cod_ibge)
        raw["exercicio"] = raw.get("exercicio", exercicio)
        bronze = _validate_bronze(raw)
        if bronze is None:
            rejected += 1
            continue
        silver = siconfi_bronze_to_silver(bronze)
        silver_list.append(silver.model_dump())
        records_out += 1

    if silver_list:
        r.setex(cache_key, CACHE_TTL, json.dumps(silver_list))

    recon = reconcile("SICONFI", records_in, records_out, str(exercicio))
    recon["rejected"] = rejected
    logger.info("SICONFI ingest %s/%s: %s", cod_ibge, exercicio, recon)
    return recon
