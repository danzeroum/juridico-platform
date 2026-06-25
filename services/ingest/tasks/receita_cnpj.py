"""
Consulta on-demand de cadastro de CNPJ (Receita Federal via API pública).

Fonte: settings.RECEITA_API_URL (padrão https://publica.cnpj.ws/cnpj) — dado
público (LGPD art. 7º, IV); CNPJ de PJ não é PII individual.

Função pura (apenas HTTP, sem Celery/Redis), usada ao vivo pelo gateway —
espelha o coletor batch services/ingest/tasks/receita.py. Enquanto o host não
estiver na allowlist de rede, degrada graciosamente para {} (ver
docs/NETWORK-ALLOWLIST.md).
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from services.ingest.pipeline.base import get_circuit_breaker
from services.shared.config import settings

logger = logging.getLogger(__name__)

_SITUACOES = {"ATIVA", "BAIXADA", "INAPTA", "SUSPENSA", "NULA"}


def _map_situacao(raw: str) -> str:
    return raw.upper().strip() if raw.upper().strip() in _SITUACOES else "ATIVA"


def _parse_date(v: Any) -> str | None:
    if not v:
        return None
    s = str(v).strip()
    if len(s) == 10 and s[4] == "-":
        return s
    if len(s) == 10 and s[2] == "/":
        d, m, y = s.split("/")
        return f"{y}-{m}-{d}"
    return None


def _nested(value: Any, key: str) -> Any:
    """Extrai `key` se `value` for dict, senão devolve o próprio valor."""
    return value.get(key) if isinstance(value, dict) else value


def _normalize(data: dict, cnpj: str) -> dict:
    """Mapeia a resposta da API pública para o cadastro normalizado."""
    cnae_principal = data.get("cnae_fiscal_principal")
    return {
        "cnpj": cnpj,
        "razao_social": data.get("razao_social") or data.get("nome") or "",
        "situacao_cadastral": _map_situacao(str(data.get("descricao_situacao_cadastral", ""))),
        "data_situacao_cadastral": _parse_date(data.get("data_situacao_cadastral")),
        "porte": data.get("descricao_porte") or data.get("porte"),
        "natureza_juridica": _nested(data.get("natureza_juridica"), "descricao"),
        "capital_social": data.get("capital_social"),
        "data_abertura": _parse_date(data.get("data_inicio_atividade") or data.get("data_abertura")),
        "municipio": _nested(data.get("municipio"), "descricao"),
        "uf": data.get("uf"),
        "cnae_fiscal": str(cnae_principal["codigo"]) if isinstance(cnae_principal, dict) else data.get("cnae_fiscal"),
        "cnae_descricao": _nested(cnae_principal, "descricao") if isinstance(cnae_principal, dict) else None,
    }


def fetch_cnpj(cnpj: str) -> dict:
    """
    Consulta o cadastro público de um CNPJ.

    Retorna o cadastro normalizado, ou {} em falha/CNPJ inválido (degradação
    graciosa enquanto o host estiver bloqueado).
    """
    digits = "".join(c for c in cnpj if c.isdigit())
    if len(digits) != 14:
        return {}

    cb = get_circuit_breaker("receita")
    if cb.is_open():
        logger.warning("CircuitBreaker Receita aberto — skip cnpj=%s", digits)
        return {}

    try:
        resp = requests.get(
            f"{settings.RECEITA_API_URL}/{digits}",
            timeout=30,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        cb.record_success()
        data = resp.json()
        return _normalize(data, digits) if isinstance(data, dict) else {}
    except Exception as exc:
        cb.record_failure()
        logger.warning("Erro ao consultar CNPJ %s na Receita: %s", digits, exc)
        return {}
