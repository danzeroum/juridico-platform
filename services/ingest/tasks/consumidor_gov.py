"""
Coletor do Consumidor.gov.br (dados abertos de reclamações).

Fonte: https://www.consumidor.gov.br/pages/dadosabertos/externo/ — arquivos CSV
públicos (delimitados por ';') com reclamações finalizadas. Agregamos por
empresa (Nome Fantasia) indicadores de reputação para enriquecer o Defensor:
total de reclamações, % de resposta, % de resolução e nota média.

Parsing/agregação são puros (testáveis sem rede). Enquanto consumidor.gov.br
estiver fora da allowlist de rede, o download degrada para {} — ver
docs/NETWORK-ALLOWLIST.md.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import unicodedata

import requests

from services.ingest.pipeline.base import get_circuit_breaker, reconcile
from services.shared.config import settings

try:
    from celery.utils.log import get_task_logger
    from ingest.celery_app import app as _celery_app

    logger = get_task_logger(__name__)
    _CELERY = True
except (ImportError, ModuleNotFoundError):
    logger = logging.getLogger(__name__)
    _celery_app = None  # type: ignore[assignment]
    _CELERY = False

CACHE_TTL = 60 * 60 * 24 * 30  # 30 dias

# Colunas do CSV de dados abertos (tolerante a ausências).
_COL_EMPRESA = "Nome Fantasia"
_COL_SITUACAO = "Situação"
_COL_RESPONDIDA = "Respondida"
_COL_NOTA = "Nota do Consumidor"


def slugify(texto: str) -> str:
    """Normaliza um nome de empresa em chave de busca (ascii, minúsculo, alfanum)."""
    norm = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return "".join(c if c.isalnum() else "-" for c in norm.lower()).strip("-")


def parse_csv(content: str) -> list[dict]:
    """Lê o CSV de reclamações (delimitado por ';')."""
    return list(csv.DictReader(io.StringIO(content), delimiter=";"))


def aggregate_reclamacoes(rows: list[dict]) -> dict[str, dict]:
    """
    Agrega reclamações por empresa. Retorna {slug: {empresa, total, respondidas,
    resolvidas, pct_resposta, pct_resolucao, nota_media}}.
    """
    agg: dict[str, dict] = {}
    notas: dict[str, list[float]] = {}

    for row in rows:
        nome = (row.get(_COL_EMPRESA) or "").strip()
        if not nome:
            continue
        slug = slugify(nome)
        bucket = agg.setdefault(
            slug, {"empresa": nome, "total": 0, "respondidas": 0, "resolvidas": 0}
        )
        bucket["total"] += 1
        if (row.get(_COL_RESPONDIDA) or "").strip().upper().startswith("S"):
            bucket["respondidas"] += 1
        # "Resolvida" exato — evita casar "Não Resolvida".
        if (row.get(_COL_SITUACAO) or "").strip().upper() == "RESOLVIDA":
            bucket["resolvidas"] += 1
        raw_nota = (row.get(_COL_NOTA) or "").strip().replace(",", ".")
        if raw_nota:
            try:
                notas.setdefault(slug, []).append(float(raw_nota))
            except ValueError:
                pass

    for slug, bucket in agg.items():
        total = bucket["total"] or 1
        bucket["pct_resposta"] = round(bucket["respondidas"] / total, 4)
        bucket["pct_resolucao"] = round(bucket["resolvidas"] / total, 4)
        lst = notas.get(slug, [])
        bucket["nota_media"] = round(sum(lst) / len(lst), 2) if lst else None

    return agg


def fetch_e_agrega(url: str) -> dict[str, dict]:
    """Baixa um CSV de dados abertos e agrega por empresa. {} em falha."""
    cb = get_circuit_breaker("consumidor_gov")
    if cb.is_open():
        logger.warning("CircuitBreaker Consumidor.gov aberto — skip %s", url)
        return {}
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        cb.record_success()
        return aggregate_reclamacoes(parse_csv(resp.text))
    except Exception as exc:
        cb.record_failure()
        logger.warning("Erro ao baixar/agregar Consumidor.gov %s: %s", url, exc)
        return {}


def _ingest_consumidor(url: str, redis_client) -> dict:
    """Agrega o CSV e persiste reputação por empresa (consumidor:{slug})."""
    agg = fetch_e_agrega(url)
    for slug, data in agg.items():
        redis_client.setex(f"consumidor:{slug}", CACHE_TTL, json.dumps(data, ensure_ascii=False))
    recon = reconcile("CONSUMIDOR_GOV", len(agg), len(agg), "dados-abertos")
    recon["empresas"] = len(agg)
    logger.info("Consumidor.gov ingest: %s", recon)
    return recon


if _CELERY:
    @_celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
    def run_ingest(self, url: str) -> dict:
        """Ingest do Consumidor.gov a partir de uma URL de CSV (Celery task)."""
        import redis as redis_lib

        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        return _ingest_consumidor(url, r)
else:
    def run_ingest(url: str) -> dict:  # type: ignore[misc]
        """Ingest do Consumidor.gov (fallback sem Celery — dev/test)."""
        import redis as redis_lib

        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        return _ingest_consumidor(url, r)
