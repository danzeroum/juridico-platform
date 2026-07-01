"""
Ingestão Receita Federal (CNPJ público) — cadência semanal.

Fonte: API pública publica.cnpj.ws — dado tornado público (LGPD art. 7º, IV).
CNPJ de PJ não é PII individual. Razão social é dado público.
"""

import json
from datetime import UTC, datetime
from typing import Any

import requests
from celery.utils.log import get_task_logger
from pydantic import ValidationError

from services.ingest.celery_app import app
from services.ingest.contracts.receita import ReceitaCnpjBronze
from services.ingest.pipeline.base import add_linage, get_circuit_breaker, reconcile
from services.ingest.pipeline.quality import receita_bronze_to_silver
from services.shared.config import settings
from services.shared.redis_client import get_redis

logger = get_task_logger(__name__)

_CACHE_TTL = 7 * 24 * 3600  # 7 dias


def _fetch_receita_cnpj(cnpj: str) -> dict[str, Any]:
    """Consulta dados cadastrais de CNPJ na Receita Federal."""
    cb = get_circuit_breaker("RECEITA")
    if cb.is_open():
        raise requests.RequestException("CircuitBreaker RECEITA OPEN")

    try:
        resp = requests.get(
            f"{settings.RECEITA_API_URL}/{cnpj}",
            timeout=30,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        cb.record_success()
        return _normalize_receita_response(data, cnpj)
    except (requests.RequestException, ValueError):
        cb.record_failure()
        raise


def _normalize_receita_response(data: dict, cnpj: str) -> dict:
    """Mapeia campos da API pública para o schema do contrato."""
    return {
        "cnpj": cnpj,
        "razao_social": data.get("razao_social") or data.get("nome") or "",
        "situacao_cadastral": _map_situacao(data.get("descricao_situacao_cadastral", "")),
        "data_situacao_cadastral": _parse_date(data.get("data_situacao_cadastral")),
        "porte": data.get("descricao_porte") or data.get("porte"),
        "natureza_juridica": data.get("natureza_juridica", {}).get("descricao") if isinstance(data.get("natureza_juridica"), dict) else data.get("natureza_juridica"),
        "capital_social": data.get("capital_social"),
        "data_abertura": _parse_date(data.get("data_inicio_atividade") or data.get("data_abertura")),
        "municipio": data.get("municipio", {}).get("descricao") if isinstance(data.get("municipio"), dict) else data.get("municipio"),
        "uf": data.get("uf"),
        "cnae_fiscal": str(data["cnae_fiscal_principal"]["codigo"]) if isinstance(data.get("cnae_fiscal_principal"), dict) else data.get("cnae_fiscal"),
        "cnaes_secundarios": [str(c.get("codigo", "")) for c in data.get("cnaes_secundarios", []) if isinstance(c, dict)],
    }


def _map_situacao(raw: str) -> str:
    raw = raw.upper().strip()
    mapping = {"ATIVA": "ATIVA", "BAIXADA": "BAIXADA", "INAPTA": "INAPTA", "SUSPENSA": "SUSPENSA", "NULA": "NULA"}
    return mapping.get(raw, "ATIVA")  # default ATIVA se desconhecido


def _parse_date(v: Any) -> str | None:
    if not v:
        return None
    s = str(v).strip()
    # formatos possíveis: YYYY-MM-DD ou DD/MM/YYYY
    if len(s) == 10 and s[4] == "-":
        return s
    if len(s) == 10 and s[2] == "/":
        parts = s.split("/")
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return None


def _validate_bronze(record: dict) -> ReceitaCnpjBronze | None:
    try:
        return ReceitaCnpjBronze(**record)
    except ValidationError as exc:
        logger.warning("RECEITA: schema inválido para CNPJ %s — %s", record.get("cnpj"), exc)
        return None


@app.task(bind=True, queue="weekly")
def run_weekly_ingest(self, cnpjs: list[str] | None = None) -> dict:
    if not cnpjs:
        logger.info("RECEITA: lista de CNPJs vazia — aguardando Fase 1c")
        return {"source": "RECEITA", "status": "no_cnpjs", "processed": 0}

    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    redis = get_redis()
    records_in = len(cnpjs)
    processed = 0
    rejected = 0

    for cnpj in cnpjs:
        digits = "".join(c for c in cnpj if c.isdigit())
        if len(digits) != 14:
            rejected += 1
            continue

        cache_key = f"receita:{digits}"
        cached = redis.get(cache_key)

        if cached:
            raw = json.loads(cached)
        else:
            try:
                raw = _fetch_receita_cnpj(digits)
                redis.setex(cache_key, _CACHE_TTL, json.dumps(raw))
            except requests.RequestException as exc:
                logger.warning("RECEITA: falha ao consultar %s — %s", digits, exc)
                continue

        raw = add_linage(raw, source="RECEITA")

        bronze = _validate_bronze(raw)
        if bronze is None:
            rejected += 1
            continue

        silver = receita_bronze_to_silver(bronze.model_dump())

        # TODO Fase 1b: persistir silver em OpenSearch (índice receita-silver-YYYY-MM)
        # TODO Fase 1b: atualizar nó CNPJ no Neo4j com dados cadastrais
        _ = silver

        processed += 1

    rec = reconcile("RECEITA", records_in, processed, date_str)
    logger.info("RECEITA ingest concluído: %s", rec)
    return {**rec, "rejected": rejected}


@app.task(bind=True, queue="weekly")
def run_weekly_ingest_single(self, cnpj: str) -> dict:
    """Consulta on-demand de um CNPJ — usada pelo gateway na Fase 1c."""
    return run_weekly_ingest(cnpjs=[cnpj])
