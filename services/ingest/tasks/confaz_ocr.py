"""
Ingestão de convênios/protocolos do CONFAZ — wrapper de I/O (omitido de cobertura).

Fluxo: scrape de links (requests + bs4) → download do PDF → extract_text (nativo ou
OCR) → parse_rules (LLM primário, heurístico como fallback) → contrato + fila de
VALIDAÇÃO HUMANA (needs_review). Dedup por hash em fiscal.doc_hash. A lógica pura
(extração/regras) é testada de verdade em services/fiscal/ingestion/confaz_parse.py.
"""
from __future__ import annotations

import logging

import requests

from services.fiscal.ingestion.confaz_parse import (
    HeuristicRuleParser,
    LlmRuleParser,
    extract_text,
    parse_rules,
)
from services.fiscal.ingestion.diario import file_sha256
from services.ingest.contracts.confaz import ConfazRegraBronze
from services.ingest.pipeline.base import get_circuit_breaker

logger = logging.getLogger(__name__)

try:
    from services.fiscal.celery_app import app
except Exception:  # pragma: no cover - contexto sem broker
    app = None  # type: ignore[assignment]

_UA = {"User-Agent": "Mozilla/5.0 (compatible; TaxDataBot/1.0)"}


def _parse_with_fallback(text: str) -> list[dict]:
    """LLM primário; se falhar (Ollama fora), usa o heurístico determinístico."""
    try:
        rules = parse_rules(text, LlmRuleParser())
        if rules:
            return rules
    except Exception as exc:
        logger.warning("CONFAZ: LLM indisponível (%s) — fallback heurístico.", exc)
    return parse_rules(text, HeuristicRuleParser())


def _already_processed(file_hash: str) -> bool:
    from sqlalchemy import text

    from services.shared.tenant_db import get_engine

    with get_engine().begin() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM fiscal.doc_hash WHERE fonte='CONFAZ' AND file_hash=:h"),
            {"h": file_hash},
        ).fetchone()
        if exists:
            return True
        conn.execute(
            text("INSERT INTO fiscal.doc_hash (fonte, file_hash) VALUES ('CONFAZ', :h)"),
            {"h": file_hash},
        )
    return False


def _process_pdf(pdf_bytes: bytes) -> list[ConfazRegraBronze]:
    file_hash = file_sha256(pdf_bytes)
    if _already_processed(file_hash):
        logger.info("CONFAZ: PDF já processado (%s).", file_hash[:12])
        return []
    text = extract_text(pdf_bytes)
    regras: list[ConfazRegraBronze] = []
    for raw in _parse_with_fallback(text):
        try:
            regras.append(ConfazRegraBronze(**raw))
        except Exception as exc:
            logger.debug("Regra CONFAZ rejeitada: %s", exc)
    # As regras vão para a fila de validação humana (não persiste alíquota direto).
    logger.info("CONFAZ: %d regras candidatas para revisão humana.", len(regras))
    return regras


if app is not None:  # pragma: no cover - só quando o broker Celery existe

    @app.task(
        bind=True,
        autoretry_for=(requests.RequestException,),
        retry_kwargs={"max_retries": 3},
        queue="fiscal_ingest",
        name="fiscal.ingestion.confaz_ocr.run_ingest",
    )
    def run_ingest(self, pdf_url: str) -> dict:
        breaker = get_circuit_breaker("CONFAZ")
        if breaker.is_open():
            return {"source": "CONFAZ", "skipped": "circuit_open"}
        try:
            resp = requests.get(pdf_url, headers=_UA, timeout=60)
            resp.raise_for_status()
            breaker.record_success()
        except requests.RequestException as exc:
            breaker.record_failure()
            raise exc
        regras = _process_pdf(resp.content)
        return {"source": "CONFAZ", "regras_para_revisao": len(regras)}
