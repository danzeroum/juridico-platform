"""
Ingest task para PNCP (Portal Nacional de Contratações Públicas).

Cadência: diária (Celery Beat).
Fonte: API PNCP (https://pncp.gov.br/api/pncp/v1/).
Cache Redis: chave pncp:{cnpj_orgao}:{ano}:{numero_controle}, TTL 24h.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime as dt

import requests
from celery.utils.log import get_task_logger
from ingest.celery_app import app
from pydantic import ValidationError

from services.ingest.contracts.pncp import (
    Modalidade,
    PncpContratoBronze,
    pncp_bronze_to_silver,
)
from services.ingest.pipeline.base import get_circuit_breaker, reconcile
from services.shared.config import settings

logger = get_task_logger(__name__)

PNCP_BASE_URL = "https://pncp.gov.br/api/pncp/v1"
CACHE_TTL = 60 * 60 * 24  # 24 horas
_PAGE_SIZE = 500

_MODALIDADE_MAP: dict[str, str] = {
    "Pregão Eletrônico":        Modalidade.PREGAO_ELETRONICO,
    "Pregão Presencial":        Modalidade.PREGAO_PRESENCIAL,
    "Concorrência Eletrônica":  Modalidade.CONCORRENCIA,
    "Concorrência":             Modalidade.CONCORRENCIA,
    "Tomada de Preços":         Modalidade.TOMADA_PRECOS,
    "Convite":                  Modalidade.CONVITE,
    "Dispensa":                 Modalidade.DISPENSA,
    "Dispensa de Licitação":    Modalidade.DISPENSA,
    "Inexigibilidade":          Modalidade.INEXIGIBILIDADE,
    "Leilão Eletrônico":        Modalidade.LEILAO,
    "Leilão":                   Modalidade.LEILAO,
}


def _map_modalidade(nome: str | None) -> str:
    if not nome:
        return Modalidade.OUTRA.value
    return _MODALIDADE_MAP.get(nome, Modalidade.OUTRA).value


def _cache_key(cnpj_orgao: str, ano: str, numero_controle: str) -> str:
    return f"pncp:{cnpj_orgao}:{ano}:{numero_controle}"


def _fetch_pncp_page(
    cnpj: str, data_inicial: str, data_final: str, pagina: int
) -> tuple[list[dict], int]:
    """Busca página de contratos PNCP. Retorna (items, total_paginas)."""
    cb = get_circuit_breaker("pncp")
    if cb.is_open():
        logger.warning("CircuitBreaker PNCP aberto — skip fetch cnpj=%s", cnpj)
        return [], 0

    try:
        resp = requests.get(
            f"{PNCP_BASE_URL}/orgaos/{cnpj}/contratos",
            params={
                "dataInicial": data_inicial,
                "dataFinal": data_final,
                "pagina": pagina,
                "tamanhoPagina": _PAGE_SIZE,
            },
            timeout=30,
        )
        resp.raise_for_status()
        cb.record_success()
        body = resp.json()
        if not isinstance(body, dict):
            return [], 0
        items = body.get("data", []) or []
        total_paginas = max(1, int(body.get("totalPaginas", 1) or 1))
        return items, total_paginas
    except Exception as exc:
        cb.record_failure()
        logger.warning("Erro ao buscar PNCP cnpj=%s pag=%d: %s", cnpj, pagina, exc)
        return [], 0


def _raw_to_bronze_dict(raw: dict, cnpj_orgao: str, ano: str) -> dict | None:
    """Mapeia resposta bruta da API PNCP para dict de PncpContratoBronze."""
    numero = (
        raw.get("numeroControlePNCP")
        or raw.get("numeroPCE")
        or raw.get("numeroControle")
    )
    if not numero:
        return None

    modalidade_info = raw.get("modalidadeContratacao") or {}
    modalidade_nome = (
        modalidade_info.get("nome") if isinstance(modalidade_info, dict) else None
    )

    objeto = raw.get("objetoContrato") or raw.get("objeto") or ""
    if not objeto:
        objeto = "Objeto não informado"

    return {
        "numero_controle":  str(numero),
        "cnpj_orgao":       cnpj_orgao,
        "cnpj_fornecedor":  raw.get("niFornecedor"),
        "objeto":           objeto,
        "modalidade":       _map_modalidade(modalidade_nome),
        "valor_contrato":   float(raw.get("valorGlobal") or raw.get("valorContrato") or 0),
        "data_publicacao":  raw.get("dataPublicacaoPncp") or raw.get("dataPublicacao") or f"{ano}-01-01",
        "data_abertura":    raw.get("dataAberturaPropostas"),
        "num_propostas":    raw.get("quantidadePropostasRecebidas"),
    }


@app.task(bind=True, max_retries=3, default_retry_delay=300)
def run_daily_ingest(self, cnpj_orgao: str, ano: int | None = None) -> dict:
    """
    Ingest diário PNCP para um órgão público.

    cnpj_orgao: CNPJ de 14 dígitos do órgão público
    ano: exercício (ex: 2024). Padrão: ano corrente.
    """
    import redis as redis_lib

    ano = ano or dt.now().year
    ano_str = str(ano)
    data_inicial = f"{ano_str}-01-01"
    data_final = f"{ano_str}-12-31"

    r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)

    records_in = 0
    records_out = 0
    rejected = 0

    pagina = 1
    total_paginas = 1
    while pagina <= min(total_paginas, 100):  # limite de segurança
        items, total_paginas = _fetch_pncp_page(
            cnpj_orgao, data_inicial, data_final, pagina
        )
        if not items:
            break
        records_in += len(items)

        for raw in items:
            try:
                bronze_dict = _raw_to_bronze_dict(raw, cnpj_orgao, ano_str)
                if bronze_dict is None:
                    rejected += 1
                    continue
                bronze = PncpContratoBronze(**bronze_dict)
            except (ValidationError, TypeError, ValueError) as exc:
                logging.warning(
                    "PNCP bronze inválido cnpj=%s: %s", cnpj_orgao, exc
                )
                rejected += 1
                continue

            silver = pncp_bronze_to_silver(bronze)
            cache_key = _cache_key(cnpj_orgao, ano_str, silver.numero_controle)
            r.setex(cache_key, CACHE_TTL, silver.model_dump_json())
            records_out += 1

        pagina += 1

    recon = reconcile("PNCP", records_in, records_out, ano_str)
    recon["rejected"] = rejected
    recon["cnpj_orgao"] = cnpj_orgao
    logger.info("PNCP ingest cnpj=%s/%s: %s", cnpj_orgao, ano_str, recon)
    return recon
