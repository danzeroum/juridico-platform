"""
Coletor do Banco Central (API SGS — Sistema Gerenciador de Séries Temporais).

Fonte: https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{N}
Indicadores macro reais para complementar o contexto do TaxPredict (o IPCA já
vem do IBGE; aqui entram SELIC e câmbio).

As funções são puras (apenas HTTP, sem Celery/Redis) e usadas ao vivo pelo
gateway. Enquanto o host `api.bcb.gov.br` estiver fora da allowlist de rede,
degradam graciosamente para {} — ver docs/NETWORK-ALLOWLIST.md.
"""
from __future__ import annotations

import logging

import requests

from services.ingest.pipeline.base import get_circuit_breaker

logger = logging.getLogger(__name__)

BCB_SGS = "https://api.bcb.gov.br/dados/serie"
# Códigos SGS: 432 = Selic meta (% a.a.); 1 = câmbio dólar (venda).
_SERIE_SELIC = 432
_SERIE_CAMBIO_USD = 1


def fetch_serie(codigo: int, n: int = 1) -> list[dict]:
    """
    Últimos `n` pontos de uma série SGS do BCB.

    Retorna [{"data": "DD/MM/AAAA", "valor": "X.XX"}, ...] ou [] em falha
    (degradação graciosa).
    """
    cb = get_circuit_breaker("bcb")
    if cb.is_open():
        logger.warning("CircuitBreaker BCB aberto — skip série %s", codigo)
        return []

    try:
        resp = requests.get(
            f"{BCB_SGS}/bcdata.sgs.{codigo}/dados/ultimos/{n}",
            params={"formato": "json"},
            timeout=30,
        )
        resp.raise_for_status()
        cb.record_success()
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception as exc:
        cb.record_failure()
        logger.warning("Erro ao buscar série SGS %s do BCB: %s", codigo, exc)
        return []


def _ultimo_valor(codigo: int) -> tuple[float | None, str | None]:
    """Valor mais recente de uma série SGS. (valor, data) ou (None, None)."""
    pontos = fetch_serie(codigo, 1)
    if not pontos:
        return None, None
    ponto = pontos[-1]
    try:
        return float(ponto["valor"]), ponto.get("data")
    except (KeyError, TypeError, ValueError):
        return None, None


def fetch_macro() -> dict:
    """
    Indicadores macro do BCB: SELIC meta (% a.a.) e câmbio dólar (venda).

    Retorna {selic, selic_data, cambio_usd, cambio_data} apenas com os campos
    disponíveis, ou {} se nada foi obtido (host bloqueado/indisponível).
    """
    out: dict = {}
    selic, selic_data = _ultimo_valor(_SERIE_SELIC)
    if selic is not None:
        out["selic"] = selic
        out["selic_data"] = selic_data
    cambio, cambio_data = _ultimo_valor(_SERIE_CAMBIO_USD)
    if cambio is not None:
        out["cambio_usd"] = cambio
        out["cambio_data"] = cambio_data
    return out
