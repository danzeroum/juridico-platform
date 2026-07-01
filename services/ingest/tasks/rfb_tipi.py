"""
Ingestão da TIPI (NCM + IPI) da Receita Federal — fonte estruturada (CSV).

Prioridade 1 do plano (baixo esforço / alto impacto): popula fiscal.ncm e
fiscal.ipi_aliquota com dados oficiais. Padrão de resiliência do ingest
(circuit breaker + retry + cache Redis) herdado de datajud.py.

Inclui scorecard de qualidade (plano §4): quarentena de alíquotas fora de faixa,
além do gate de reconciliação. Coberto por integração (ver pyproject omit).
"""
from __future__ import annotations

import csv
import io
import logging
import os

import requests

from services.ingest.contracts.tipi import TipiBronze
from services.ingest.pipeline.base import (
    add_linage,
    get_circuit_breaker,
    reconcile,
)

logger = logging.getLogger(__name__)

try:
    from services.ingest.celery_app import app
except Exception:  # pragma: no cover - contexto sem broker
    app = None  # type: ignore[assignment]

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_ALIQUOTA_MIN, _ALIQUOTA_MAX = 0.0, 400.0  # IPI fora dessa faixa → quarentena


def _fetch_csv(url: str) -> str:
    resp = requests.get(url, headers={"User-Agent": _UA}, timeout=60)
    resp.raise_for_status()
    resp.encoding = "latin1"  # arquivos gov.br costumam ser ISO-8859-1
    return resp.text


def _parse_rows(csv_text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(csv_text), delimiter=";")
    return list(reader)


def _to_bronze(raw: dict) -> TipiBronze | None:
    try:
        aliq_raw = (raw.get("ALIQUOTA_IPI") or raw.get("aliquota") or "").replace(",", ".").strip()
        aliquota = float(aliq_raw) if aliq_raw and aliq_raw.upper() != "NT" else None
        record = add_linage(
            {
                "ncm_codigo": (raw.get("CODIGO") or raw.get("ncm") or "").replace(".", "").strip(),
                "descricao": (raw.get("DESCRICAO") or raw.get("descricao") or "").strip(),
                "aliquota_ipi": aliquota,
                "excecao": (raw.get("EX") or None),
            },
            source="TIPI",
        )
        return TipiBronze(**record)
    except Exception as exc:
        logger.debug("Linha TIPI rejeitada: %s", exc)
        return None


def _quality_ok(bronze: TipiBronze) -> bool:
    """Scorecard: alíquota de IPI deve estar em faixa plausível."""
    if bronze.aliquota_ipi is None:
        return True
    return _ALIQUOTA_MIN <= bronze.aliquota_ipi <= _ALIQUOTA_MAX


def _upsert(rows: list[TipiBronze]) -> int:
    from sqlalchemy import text

    from services.shared.tenant_db import get_engine

    with get_engine().begin() as conn:
        for b in rows:
            # NCM: insere a vigência atual se ainda não existir (idempotente).
            conn.execute(
                text(
                    "INSERT INTO fiscal.ncm (ncm_codigo, descricao, capitulo, source, transform_version) "
                    "SELECT :c, :d, :cap, 'TIPI', :tv "
                    "WHERE NOT EXISTS (SELECT 1 FROM fiscal.ncm "
                    "  WHERE ncm_codigo = :c AND vigencia @> CURRENT_DATE)"
                ),
                {"c": b.ncm_codigo, "d": b.descricao, "cap": b.capitulo, "tv": b.transform_version},
            )
            if b.aliquota_ipi is not None:
                conn.execute(
                    text(
                        "INSERT INTO fiscal.ipi_aliquota "
                        "(ncm_codigo, excecao, aliquota_pct, source, transform_version) "
                        "VALUES (:c, :ex, :a, 'TIPI', :tv) "
                        "ON CONFLICT (ncm_codigo, excecao) DO UPDATE "
                        "SET aliquota_pct = EXCLUDED.aliquota_pct, ingested_at = NOW()"
                    ),
                    {"c": b.ncm_codigo, "ex": b.excecao, "a": b.aliquota_ipi, "tv": b.transform_version},
                )
    return len(rows)


def _run(url: str) -> dict:
    breaker = get_circuit_breaker("TIPI")
    if breaker.is_open():
        logger.warning("TIPI: circuit breaker aberto — pulando execução.")
        return {"source": "TIPI", "skipped": "circuit_open"}

    try:
        csv_text = _fetch_csv(url)
        breaker.record_success()
    except requests.RequestException as exc:
        breaker.record_failure()
        raise exc

    raw_rows = _parse_rows(csv_text)
    records_in = len(raw_rows)
    valid: list[TipiBronze] = []
    quarantined = 0
    for raw in raw_rows:
        bronze = _to_bronze(raw)
        if bronze is None:
            continue
        if not _quality_ok(bronze):
            quarantined += 1
            continue
        valid.append(bronze)

    processed = _upsert(valid)
    rec = reconcile("TIPI", records_in, processed, "current")
    logger.info("TIPI: %d processados, %d em quarentena", processed, quarantined)
    return {**rec, "quarantined": quarantined}


if app is not None:  # pragma: no cover - só quando o broker Celery existe

    @app.task(
        bind=True,
        autoretry_for=(requests.RequestException,),
        retry_kwargs={"max_retries": 5},
        queue="monthly",
        name="ingest.tasks.rfb_tipi.run_ingest",
    )
    def run_ingest(self, url: str | None = None) -> dict:
        target = url or os.getenv(
            "TIPI_CSV_URL",
            "https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/tipi/tipi.csv",
        )
        return _run(target)
