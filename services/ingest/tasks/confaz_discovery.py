"""
Descoberta de convênios do CONFAZ — wrapper de I/O (omitido de cobertura).

Busca a página de índice do CONFAZ, extrai os links de PDF (convênios/protocolos)
e enfileira o confaz_ocr por link. Roda no worker fiscal (fila fiscal_ingest). A
lógica pura (parse do índice) é testada em services/fiscal/ingestion/confaz_index.py.
"""
from __future__ import annotations

import logging
import os

import requests

from services.fiscal.ingestion.confaz_index import parse_convenio_links
from services.ingest.pipeline.base import get_circuit_breaker

logger = logging.getLogger(__name__)

try:
    from services.fiscal.celery_app import app
except Exception:  # pragma: no cover - contexto sem broker
    app = None  # type: ignore[assignment]

_UA = {"User-Agent": "Mozilla/5.0 (compatible; TaxDataBot/1.0)"}
_DEFAULT_INDEX = "https://www.confaz.fazenda.gov.br/legislacao/convenios"


def _run(index_url: str) -> dict:
    breaker = get_circuit_breaker("CONFAZ-INDEX")
    if breaker.is_open():
        return {"source": "CONFAZ-INDEX", "skipped": "circuit_open"}
    try:
        resp = requests.get(index_url, headers=_UA, timeout=60)
        resp.raise_for_status()
        breaker.record_success()
    except requests.RequestException as exc:
        breaker.record_failure()
        raise exc

    links = parse_convenio_links(resp.text, index_url)
    enfileirados = 0
    if app is not None:
        for url in links:
            app.send_task(
                "fiscal.ingestion.confaz_ocr.run_ingest",
                args=[url],
                queue="fiscal_ingest",
            )
            enfileirados += 1
    logger.info("CONFAZ-INDEX: %d links descobertos, %d enfileirados.", len(links), enfileirados)
    return {"source": "CONFAZ-INDEX", "links": len(links), "enqueued": enfileirados}


if app is not None:  # pragma: no cover - só quando o broker Celery existe

    @app.task(
        bind=True,
        autoretry_for=(requests.RequestException,),
        retry_kwargs={"max_retries": 3},
        queue="fiscal_ingest",
        name="fiscal.ingestion.confaz_discovery.run_ingest",
    )
    def run_ingest(self, index_url: str | None = None) -> dict:
        return _run(index_url or os.getenv("CONFAZ_INDEX_URL", _DEFAULT_INDEX))
