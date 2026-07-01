"""
Ingest task para indicadores da ABJ (Associação Brasileira de Jurimetria).

Cadência: mensal / on-demand (datasets curados, periodicidade baixa).
Fonte: datasets abjData / observatórios (CSV). Base legal: dado público.

LICENÇA / GOVERNANÇA:
- Ingestão DESLIGADA por padrão (settings.ABJ_ENABLED). Habilitar só após
  confirmar redistribuição comercial dos datasets e registrar base legal na ROPA.
- Enquanto desligada, a ABJ serve como fonte de VALIDAÇÃO cruzada e SEMENTE das
  tabelas TPU — o valor de jurimetria vem primariamente do DATAJUD (já ingerido).

Destino:
- silver → OpenSearch (`abj-silver`) via persist_silver;
- landing → jurimetria.abj_indicador_raw (Postgres, tabela global — get_engine()).
"""
from __future__ import annotations

import csv
import io
import logging

import requests
from celery.utils.log import get_task_logger
from pydantic import ValidationError

from services.ingest.celery_app import app
from services.ingest.contracts.abj import AbjIndicadorBronze, abj_bronze_to_silver
from services.ingest.pipeline.base import get_circuit_breaker, persist_silver, reconcile
from services.shared.config import settings

logger = get_task_logger(__name__)


def _fetch_abj_csv() -> list[dict]:
    """Baixa o CSV de indicadores da ABJ. Retorna lista de dicts (linhas)."""
    if not settings.ABJ_DATA_URL:
        logger.info("ABJ: ABJ_DATA_URL vazio — nada a buscar (use semente/seed).")
        return []

    cb = get_circuit_breaker("ABJ")
    if cb.is_open():
        logger.warning("CircuitBreaker ABJ aberto — skip fetch")
        return []
    try:
        resp = requests.get(settings.ABJ_DATA_URL, timeout=60)
        resp.raise_for_status()
        cb.record_success()
        reader = csv.DictReader(io.StringIO(resp.text))
        return list(reader)
    except Exception as exc:  # noqa: BLE001
        cb.record_failure()
        logger.warning("Erro ao buscar ABJ: %s", exc)
        return []


def _validate_bronze(raw: dict) -> AbjIndicadorBronze | None:
    try:
        return AbjIndicadorBronze(**raw)
    except (ValidationError, TypeError) as exc:
        logging.warning("ABJ bronze inválido: %s | %s", exc, raw)
        return None


def _upsert_landing(silver_rows: list[dict]) -> int:
    """Upsert em jurimetria.abj_indicador_raw (tabela global, sem tenant)."""
    if not silver_rows:
        return 0
    from sqlalchemy import text

    from services.shared.tenant_db import get_engine

    stmt = text(
        """
        INSERT INTO jurimetria.abj_indicador_raw
            (tribunal, classe_cnj, assunto_cnj, periodo, tempo_medio_dias,
             taxa_congestionamento, casos_novos, casos_baixados, casos_pendentes,
             source, transform_version)
        VALUES
            (:tribunal, :classe_cnj, :assunto_cnj, :periodo, :tempo_medio_dias,
             :taxa_congestionamento, :casos_novos, :casos_baixados, :casos_pendentes,
             :source, :transform_version)
        ON CONFLICT (tribunal, COALESCE(classe_cnj, ''), COALESCE(assunto_cnj, ''), periodo)
        DO UPDATE SET
            tempo_medio_dias      = EXCLUDED.tempo_medio_dias,
            taxa_congestionamento = EXCLUDED.taxa_congestionamento,
            casos_novos           = EXCLUDED.casos_novos,
            casos_baixados        = EXCLUDED.casos_baixados,
            casos_pendentes       = EXCLUDED.casos_pendentes,
            ingested_at           = NOW()
        """
    )
    engine = get_engine()
    with engine.begin() as conn:
        for row in silver_rows:
            conn.execute(stmt, {
                "tribunal": row.get("tribunal"),
                "classe_cnj": row.get("classe_cnj"),
                "assunto_cnj": row.get("assunto_cnj"),
                "periodo": row.get("periodo"),
                "tempo_medio_dias": row.get("tempo_medio_dias"),
                "taxa_congestionamento": row.get("taxa_congestionamento"),
                "casos_novos": row.get("casos_novos"),
                "casos_baixados": row.get("casos_baixados"),
                "casos_pendentes": row.get("casos_pendentes"),
                "source": "ABJ",
                "transform_version": row.get("transform_version", "1.0.0"),
            })
    return len(silver_rows)


@app.task(bind=True, max_retries=3, default_retry_delay=300, queue="monthly")
def run_monthly_ingest(self, date: str | None = None) -> dict:
    """Ingest mensal dos indicadores ABJ. No-op se ABJ_ENABLED=false."""
    if not settings.ABJ_ENABLED:
        logger.info("ABJ desabilitada (ABJ_ENABLED=false) — ingest ignorada.")
        return {"source": "ABJ", "status": "disabled"}

    date = date or "on-demand"
    raw_list = _fetch_abj_csv()
    records_in = len(raw_list)
    silver_rows: list[dict] = []
    rejected = 0

    for raw in raw_list:
        bronze = _validate_bronze(raw)
        if bronze is None:
            rejected += 1
            continue
        silver_rows.append(abj_bronze_to_silver(bronze).model_dump())

    persist_result = persist_silver(
        source="ABJ",
        date_str=date,
        bronze_records=silver_rows,
        silver_records=silver_rows,
        opensearch_index="abj-silver",
        graph_writer=None,
        id_field="tribunal",
    )
    landed = _upsert_landing(silver_rows)

    rec = reconcile("ABJ", records_in, len(silver_rows), date)
    rec.update({"rejected": rejected, "landed": landed, "persist": persist_result})
    logger.info("ABJ ingest: %s", rec)
    return rec
