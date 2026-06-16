"""
ComplianceRadar — monitor de indicadores municipais.

Avalia as regras de `compliance/rules.py` contra dados públicos ingeridos
(SICONFI, CAGED, SNIS, IBGE) e gera AlertEnvelopes para publicação.

Fontes usadas nesta fase:
  - SICONFI: arrecadação municipal
  - CAGED: emprego formal
  - SNIS: cobertura de saneamento
  - IBGE: indicadores socioeconômicos

DATASUS (dados de saúde — sensível art. 11 LGPD) EXCLUÍDO desta fase.
Ver PD-06 em Pendencia.md — requer parecer do DPO antes de Fase 3b.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from services.compliance.rules import ALERT_RULES
from services.shared.contracts.alerts import AlertEnvelope, Channel, Severity


def _map_severity(raw: str) -> Severity:
    mapping = {
        "CRITICAL": Severity.CRITICAL,
        "HIGH": Severity.HIGH,
        "MEDIUM": Severity.MEDIUM,
        "LOW": Severity.LOW,
    }
    return mapping.get(raw.upper(), Severity.MEDIUM)


def _map_channels(raw: list[str]) -> list[Channel]:
    mapping = {
        "webhook": Channel.WEBHOOK,
        "email": Channel.EMAIL,
        "slack": Channel.SLACK,
        "whatsapp": Channel.WHATSAPP,
    }
    return [mapping[c] for c in raw if c in mapping]


@dataclass
class MunicipioIndicadores:
    """Snapshot de indicadores de um município para avaliação de regras."""

    cod_ibge: str
    referencia: str  # "YYYY-MM" (período dos dados)
    delta_arrecadacao_yoy: float | None = None   # variação YoY da arrecadação
    delta_emprego_yoy: float | None = None        # variação YoY de emprego formal
    cobertura_agua_pct: float | None = None
    cobertura_esgoto_pct: float | None = None
    idhm: float | None = None
    pib_per_capita: float | None = None
    source_lag_days: int = -1  # máximo lag entre as fontes (dias)
    source_date: str | None = None  # YYYY-MM-DD da publicação mais recente
    sources_missing: list[str] | None = None


def _eval_arrecadacao_critica(ind: MunicipioIndicadores) -> bool:
    """CC: arrecadacao_critica — queda > 20% YoY E emprego caindo > 10%."""
    if ind.delta_arrecadacao_yoy is None or ind.delta_emprego_yoy is None:
        return False
    return ind.delta_arrecadacao_yoy < -0.20 and ind.delta_emprego_yoy < -0.10


def _eval_saneamento_baixo(ind: MunicipioIndicadores) -> bool:
    """CC: saneamento_baixo — cobertura água < 50% E esgoto < 30%."""
    if ind.cobertura_agua_pct is None or ind.cobertura_esgoto_pct is None:
        return False
    return ind.cobertura_agua_pct < 50.0 and ind.cobertura_esgoto_pct < 30.0


# Mapa de rule_id → função de avaliação
_RULE_EVALUATORS: dict[str, Any] = {
    "arrecadacao_critica": _eval_arrecadacao_critica,
    "saneamento_baixo": _eval_saneamento_baixo,
}


def evaluate_municipio(ind: MunicipioIndicadores) -> list[AlertEnvelope]:
    """
    Avalia todas as regras contra os indicadores de um município.

    Retorna lista de AlertEnvelopes prontos para publicar via AlertPublisher.
    Envelopes com `enrichment=True` devem ser enriquecidos pelo worker antes da entrega.
    """
    envelopes: list[AlertEnvelope] = []
    occurred_at = datetime.now(UTC)

    for rule in ALERT_RULES:
        rule_id = rule["id"]
        evaluator = _RULE_EVALUATORS.get(rule_id)
        if evaluator is None:
            continue
        if not evaluator(ind):
            continue

        alert_id = str(uuid.uuid4())
        dedup_key = f"{rule_id}:{ind.cod_ibge}:{ind.referencia}"

        payload: dict[str, Any] = {
            "cod_ibge": ind.cod_ibge,
            "referencia": ind.referencia,
            "source_lag_days": ind.source_lag_days,
        }
        if ind.delta_arrecadacao_yoy is not None:
            payload["delta_arrecadacao_yoy"] = round(ind.delta_arrecadacao_yoy, 4)
        if ind.delta_emprego_yoy is not None:
            payload["delta_emprego_yoy"] = round(ind.delta_emprego_yoy, 4)
        if ind.cobertura_agua_pct is not None:
            payload["cobertura_agua_pct"] = round(ind.cobertura_agua_pct, 2)
        if ind.cobertura_esgoto_pct is not None:
            payload["cobertura_esgoto_pct"] = round(ind.cobertura_esgoto_pct, 2)
        if ind.sources_missing:
            payload["sources_missing"] = ind.sources_missing

        envelope = AlertEnvelope(
            alert_id=alert_id,
            dedup_key=dedup_key,
            rule_id=rule_id,
            severity=_map_severity(rule["severity"]),
            subject_ref={"municipio_ibge": ind.cod_ibge},
            payload=payload,
            channels=_map_channels(rule["channels"]),
            occurred_at=occurred_at,
            enrichment=bool(rule.get("enrichment", False)),
        )
        envelopes.append(envelope)

    return envelopes


def build_indicadores_from_cache(
    cod_ibge: str,
    referencia: str,
    siconfi_atual: dict | None,
    siconfi_anterior: dict | None,
    caged_atual: dict | None,
    caged_anterior: dict | None,
    snis: dict | None,
) -> MunicipioIndicadores:
    """
    Constrói MunicipioIndicadores a partir dos dados em cache Redis.

    Todos os parâmetros podem ser None (dado indisponível).
    Indicadores ausentes são deixados como None — as regras os ignoram.
    """
    delta_arr = None
    if siconfi_atual and siconfi_anterior:
        v_atual = siconfi_atual.get("valor", 0.0)
        v_ant = siconfi_anterior.get("valor", 0.0)
        if v_ant and v_ant != 0:
            delta_arr = (v_atual - v_ant) / abs(v_ant)

    delta_emp = None
    if caged_atual and caged_anterior:
        s_atual = caged_atual.get("saldo_admissoes_desligamentos", 0)
        s_ant = caged_anterior.get("saldo_admissoes_desligamentos", 0)
        base = abs(s_ant) or 1
        delta_emp = (s_atual - s_ant) / base

    cob_agua = snis.get("cobertura_agua_pct") if snis else None
    cob_esgoto = snis.get("cobertura_esgoto_pct") if snis else None

    sources_missing = []
    if siconfi_atual is None:
        sources_missing.append("SICONFI")
    if caged_atual is None:
        sources_missing.append("CAGED")
    if snis is None:
        sources_missing.append("SNIS")

    lag = snis.get("lag_days", -1) if snis else -1
    source_date = snis.get("source_date") if snis else None

    return MunicipioIndicadores(
        cod_ibge=cod_ibge,
        referencia=referencia,
        delta_arrecadacao_yoy=delta_arr,
        delta_emprego_yoy=delta_emp,
        cobertura_agua_pct=cob_agua,
        cobertura_esgoto_pct=cob_esgoto,
        source_lag_days=lag,
        source_date=source_date,
        sources_missing=sources_missing,
    )
