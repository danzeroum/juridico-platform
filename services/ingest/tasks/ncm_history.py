"""
Ingestão do histórico de migração de NCM → fiscal.ncm_migracao (wrapper de I/O).

A lógica pura (parse + resolução temporal) é testada de verdade em
services/fiscal/ingestion/ncm_history.py. Aqui só o download + upsert idempotente.
"""
from __future__ import annotations

import logging

import requests

from services.fiscal.ingestion.ncm_history import parse_migracao

logger = logging.getLogger(__name__)

try:
    from services.fiscal.celery_app import app
except Exception:  # pragma: no cover - contexto sem broker
    app = None  # type: ignore[assignment]

_UA = {"User-Agent": "Mozilla/5.0 (compatible; TaxDataBot/1.0)"}


def _upsert(rows: list[dict]) -> int:
    from sqlalchemy import text

    from services.shared.tenant_db import get_engine

    with get_engine().begin() as conn:
        for r in rows:
            conn.execute(
                text(
                    "INSERT INTO fiscal.ncm_migracao "
                    "(ncm_origem, ncm_destino, vigencia_inicio, vigencia_fim, ato_legal) "
                    "SELECT :o, :d, :vi::date, :vf::date, :ato "
                    "WHERE NOT EXISTS (SELECT 1 FROM fiscal.ncm_migracao "
                    "  WHERE ncm_origem = :o AND COALESCE(ncm_destino,'') = COALESCE(:d,'') "
                    "    AND COALESCE(vigencia_inicio, DATE '0001-01-01') "
                    "        = COALESCE(:vi::date, DATE '0001-01-01'))"
                ),
                {"o": r["ncm_origem"], "d": r["ncm_destino"], "vi": r["vigencia_inicio"],
                 "vf": r["vigencia_fim"], "ato": r["ato_legal"]},
            )
    return len(rows)


def _run(csv_text: str) -> dict:
    rows = parse_migracao(csv_text)
    n = _upsert(rows)
    logger.info("NCM migração: %d linhas processadas.", n)
    return {"source": "NCM_MIGRACAO", "processed": n}


if app is not None:  # pragma: no cover - só quando o broker Celery existe

    @app.task(
        bind=True,
        autoretry_for=(requests.RequestException,),
        retry_kwargs={"max_retries": 3},
        queue="fiscal_ingest",
        name="fiscal.ingestion.ncm_history.run_ingest",
    )
    def run_ingest(self, url: str) -> dict:
        resp = requests.get(url, headers=_UA, timeout=60)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return _run(resp.text)
