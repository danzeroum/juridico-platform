"""
LicitaWatch — monitor de licitações públicas (PNCP).

Detecta padrões de risco em contratos de órgãos públicos:
  LL01: Concentração de fornecedor (> 70% ao mesmo vencedor)
  LL02: Dispensa/inexigibilidade excessiva (> 30%)
  LL03: Predominância de único proponente (> 50%)
  LL04: Prazo de abertura curto (< 5 dias em > 20% dos contratos)
"""
from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime

from services.ingest.contracts.pncp import PncpContratoSilver
from services.licitawatch.rules import LICITAWATCH_RULES
from services.shared.contracts.alerts import AlertEnvelope, Channel, Severity

_PRAZO_CURTO_DIAS = 5

_SEVERITY_MAP = {
    "CRITICO": Severity.CRITICAL,
    "ALTO": Severity.HIGH,
    "MEDIO": Severity.MEDIUM,
    "BAIXO": Severity.LOW,
}


@dataclass
class LicitacaoIndicadores:
    """Métricas agregadas de um órgão para avaliação das regras LL01–LL04."""

    cnpj_orgao:          str
    referencia:          str      # "YYYY"
    total_contratos:     int      = 0
    pct_mesmo_vencedor:  float | None = None  # máx share para um único fornecedor
    pct_dispensa:        float    = 0.0
    pct_unico_proponente: float   = 0.0
    pct_prazo_curto:     float    = 0.0
    valor_total:         float    = 0.0


def evaluate_licitacoes(ind: LicitacaoIndicadores) -> list[AlertEnvelope]:
    """Avalia regras LL01–LL04. Retorna AlertEnvelopes para regras violadas."""
    if ind.total_contratos == 0:
        return []

    field_values: dict[str, float | None] = {
        "pct_mesmo_vencedor":   ind.pct_mesmo_vencedor,
        "pct_dispensa":         ind.pct_dispensa,
        "pct_unico_proponente": ind.pct_unico_proponente,
        "pct_prazo_curto":      ind.pct_prazo_curto,
    }

    envelopes: list[AlertEnvelope] = []
    for rule in LICITAWATCH_RULES:
        value = field_values.get(rule["field"])
        if value is None:
            continue
        if value <= rule["threshold"]:
            continue

        severity = _SEVERITY_MAP.get(rule["severity"], Severity.MEDIUM)
        dedup_key = f"{rule['id']}:{ind.cnpj_orgao}:{ind.referencia}"

        envelopes.append(AlertEnvelope(
            alert_id=str(uuid.uuid4()),
            dedup_key=dedup_key,
            rule_id=rule["id"],
            severity=severity,
            subject_ref={"cnpj": ind.cnpj_orgao},  # CNPJ de órgão público — não é PII
            payload={
                "total_contratos":  ind.total_contratos,
                "valor_observado":  round(value, 4),
                "threshold":        rule["threshold"],
                "referencia":       ind.referencia,
            },
            channels=[Channel.WEBHOOK],
            occurred_at=datetime.now(UTC),
        ))

    return envelopes


def build_indicadores_from_silver(
    cnpj_orgao: str,
    referencia: str,
    contratos: list[PncpContratoSilver],
) -> LicitacaoIndicadores:
    """Agrega lista de PncpContratoSilver em LicitacaoIndicadores."""
    if not contratos:
        return LicitacaoIndicadores(cnpj_orgao=cnpj_orgao, referencia=referencia)

    total = len(contratos)
    valor_total = sum(c.valor_contrato for c in contratos)

    # LL01 — concentração de vencedor
    fornecedores = [c.cnpj_fornecedor for c in contratos if c.cnpj_fornecedor]
    pct_mesmo_vencedor: float | None = None
    if fornecedores:
        mais_freq = Counter(fornecedores).most_common(1)[0][1]
        pct_mesmo_vencedor = round(mais_freq / total, 4)

    # LL02 — dispensa/inexigibilidade
    n_dispensa = sum(1 for c in contratos if c.is_dispensa)
    pct_dispensa = round(n_dispensa / total, 4)

    # LL03 — único proponente
    n_unico = sum(1 for c in contratos if c.is_unico_proponente)
    pct_unico = round(n_unico / total, 4)

    # LL04 — prazo curto (< 5 dias)
    n_prazo = sum(
        1 for c in contratos
        if c.prazo_abertura_dias is not None and c.prazo_abertura_dias < _PRAZO_CURTO_DIAS
    )
    pct_prazo = round(n_prazo / total, 4)

    return LicitacaoIndicadores(
        cnpj_orgao=cnpj_orgao,
        referencia=referencia,
        total_contratos=total,
        pct_mesmo_vencedor=pct_mesmo_vencedor,
        pct_dispensa=pct_dispensa,
        pct_unico_proponente=pct_unico,
        pct_prazo_curto=pct_prazo,
        valor_total=round(valor_total, 2),
    )
