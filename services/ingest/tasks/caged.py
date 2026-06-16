"""
Ingest task para CAGED (Cadastro Geral de Empregados e Desempregados).

Cadência: mensal (Celery Beat).
Fonte: API pública do Novo CAGED (MTE/MTPS).
Cache Redis: chave caged:{cnpj}:{competencia}, TTL 30 dias.
"""
from __future__ import annotations

import json
import logging

import requests
from celery.utils.log import get_task_logger
from ingest.celery_app import app
from pydantic import ValidationError

from services.ingest.contracts.caged import (
    TRANSFORM_VERSION,
    CagedEstabelecimentoBronze,
    CagedEstabelecimentoSilver,
)
from services.ingest.pipeline.base import get_circuit_breaker, reconcile
from services.shared.config import settings

logger = get_task_logger(__name__)

CAGED_BASE_URL = "https://api.dados.gov.br/v1/conjuntos-dados/novo-caged"
CACHE_TTL = 60 * 60 * 24 * 30  # 30 dias


def _cache_key(cnpj: str, competencia: str) -> str:
    return f"caged:{cnpj}:{competencia}"


def _fetch_caged_api(cnpj: str, competencia: str) -> list[dict]:
    """Busca dados CAGED via API pública. Retorna lista de registros brutos."""
    cb = get_circuit_breaker("caged")
    if cb.is_open():
        logger.warning("CircuitBreaker CAGED aberto — skip fetch")
        return []

    try:
        url = f"{CAGED_BASE_URL}/estabelecimento"
        resp = requests.get(
            url,
            params={"cnpj": cnpj, "competencia": competencia},
            timeout=30,
        )
        resp.raise_for_status()
        cb.record_success()
        data = resp.json()
        return data if isinstance(data, list) else data.get("data", [])
    except Exception as exc:
        cb.record_failure()
        logger.warning("Erro ao buscar CAGED %s/%s: %s", cnpj, competencia, exc)
        return []


def _validate_bronze(raw: dict) -> CagedEstabelecimentoBronze | None:
    try:
        return CagedEstabelecimentoBronze(**raw)
    except (ValidationError, TypeError) as exc:
        logging.warning("CAGED bronze inválido: %s | %s", exc, raw)
        return None


def _bronze_to_silver(b: CagedEstabelecimentoBronze) -> CagedEstabelecimentoSilver:
    return CagedEstabelecimentoSilver(
        competencia=b.competencia,
        cnpj_estabelecimento=b.cnpj_estabelecimento,
        uf=b.uf,
        municipio=b.municipio,
        secao_cnae=b.secao_cnae,
        saldo_admissoes_desligamentos=b.saldo_admissoes_desligamentos,
        admissoes=b.admissoes or 0,
        desligamentos=b.desligamentos or 0,
        salario_medio_normalizado=b.salario_medio or 0.0,
        is_crescendo=b.saldo_admissoes_desligamentos > 0,
        ingested_at=b.ingested_at,
        transform_version=TRANSFORM_VERSION,
    )


@app.task(bind=True, max_retries=3, default_retry_delay=120)
def run_monthly_ingest(self, competencia: str, cnpjs: list[str]) -> dict:
    """
    Ingest mensal CAGED para lista de CNPJs.

    competencia: "YYYY-MM"
    cnpjs: lista de CNPJs (14 dígitos)
    """
    import redis as redis_lib

    r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
    records_in = 0
    records_out = 0
    rejected = 0

    for cnpj in cnpjs:
        cache_key = _cache_key(cnpj, competencia)
        cached = r.get(cache_key)
        if cached:
            records_out += 1
            continue

        raw_list = _fetch_caged_api(cnpj, competencia)
        records_in += len(raw_list)

        for raw in raw_list:
            bronze = _validate_bronze(raw)
            if bronze is None:
                rejected += 1
                continue
            silver = _bronze_to_silver(bronze)
            r.setex(cache_key, CACHE_TTL, json.dumps(silver.model_dump()))
            records_out += 1

    recon = reconcile("CAGED", records_in, records_out, competencia)
    recon["rejected"] = rejected
    logger.info("CAGED ingest %s: %s", competencia, recon)
    return recon


@app.task(bind=True, max_retries=3, default_retry_delay=120)
def run_monthly_ingest_single(self, cnpj: str, competencia: str) -> dict:
    """Ingest de um único CNPJ para uma competência."""
    return run_monthly_ingest(self, competencia=competencia, cnpjs=[cnpj])
