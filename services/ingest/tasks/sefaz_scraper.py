"""
Scraper de alíquotas internas de ICMS (SP/RJ/MG) — wrapper de I/O (omitido de cobertura).

Fluxo: fetch_html (Playwright, preferir API REST interna quando existir) → parse
(bs4) → validação de contrato + scorecard (quarentena de outliers) → upsert em
fiscal.icms_interno. A lógica pura (parse/scorecard) é testada de verdade em
services/fiscal/ingestion/sefaz_parse.py.
"""
from __future__ import annotations

import logging

from services.fiscal.ingestion.browser import fetch_html
from services.fiscal.ingestion.sefaz_parse import parse_aliquota_table
from services.ingest.contracts.sefaz import SefazAliquotaBronze
from services.ingest.pipeline.base import get_circuit_breaker, reconcile

logger = logging.getLogger(__name__)

try:
    from services.ingest.celery_app import app
except Exception:  # pragma: no cover - contexto sem broker
    app = None  # type: ignore[assignment]

# Portais por UF (default page de tabela de alíquotas). Preferir endpoint REST interno.
PORTAIS = {
    "SP": "https://portal.fazenda.sp.gov.br/servicos/ricms/",
    "RJ": "https://portal.fazenda.rj.gov.br/legislacao/aliquotas-icms/",
    "MG": "https://www.fazenda.mg.gov.br/empresas/legislacao_tributaria/aliquotas/",
}


def _to_bronze(row: dict) -> SefazAliquotaBronze | None:
    try:
        return SefazAliquotaBronze(**row)
    except Exception as exc:  # outlier/inválido → quarentena
        logger.debug("Linha SEFAZ rejeitada: %s", exc)
        return None


def _upsert(rows: list[SefazAliquotaBronze]) -> int:
    from sqlalchemy import text

    from services.shared.tenant_db import get_engine

    with get_engine().begin() as conn:
        for b in rows:
            # Alíquota geral (ncm_prefix None) ou por prefixo — insere vigência atual
            # se ainda não existir para (uf, prefix).
            conn.execute(
                text(
                    "INSERT INTO fiscal.icms_interno "
                    "(uf, ncm_prefix, aliquota_pct, fcp_pct, fundamento_legal, source, transform_version) "
                    "SELECT :uf, :px, :a, :fcp, :f, 'SEFAZ', :tv "
                    "WHERE NOT EXISTS (SELECT 1 FROM fiscal.icms_interno "
                    "  WHERE uf = :uf AND COALESCE(ncm_prefix,'') = COALESCE(:px,'') "
                    "    AND vigencia @> CURRENT_DATE)"
                ),
                {"uf": b.uf, "px": b.ncm_prefix, "a": b.aliquota_pct, "fcp": b.fcp_pct,
                 "f": b.fundamento_legal, "tv": b.transform_version},
            )
    return len(rows)


def _run(uf: str, url: str | None = None) -> dict:
    breaker = get_circuit_breaker(f"SEFAZ-{uf}")
    if breaker.is_open():
        logger.warning("SEFAZ-%s: circuit breaker aberto — pulando.", uf)
        return {"source": f"SEFAZ-{uf}", "skipped": "circuit_open"}

    target = url or PORTAIS[uf]
    try:
        html = fetch_html(target, wait_selector="table")
        breaker.record_success()
    except Exception as exc:
        breaker.record_failure()
        raise exc

    raw = parse_aliquota_table(html, uf)
    records_in = len(raw)
    valid = [b for b in (_to_bronze(r) for r in raw) if b is not None]
    processed = _upsert(valid)
    rec = reconcile(f"SEFAZ-{uf}", records_in, processed, "current")
    logger.info("SEFAZ-%s: %d processados de %d", uf, processed, records_in)
    return rec


if app is not None:  # pragma: no cover - só quando o broker Celery existe

    @app.task(bind=True, queue="weekly", name="ingest.tasks.sefaz_scraper.run_ingest")
    def run_ingest(self, uf: str, url: str | None = None) -> dict:
        return _run(uf.upper(), url)
