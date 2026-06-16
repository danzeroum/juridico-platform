"""Testes do ComplianceRadar monitor."""
from __future__ import annotations

import pytest

from services.compliance.monitor import (
    MunicipioIndicadores,
    build_indicadores_from_cache,
    evaluate_municipio,
)
from services.shared.contracts.alerts import AlertEnvelope, Severity

COD_IBGE = "3550308"
REF = "2024-06"


# ---------------------------------------------------------------------------
# evaluate_municipio — regra arrecadacao_critica
# ---------------------------------------------------------------------------

def test_arrecadacao_critica_dispara():
    ind = MunicipioIndicadores(
        cod_ibge=COD_IBGE,
        referencia=REF,
        delta_arrecadacao_yoy=-0.25,  # < -20%
        delta_emprego_yoy=-0.15,      # < -10%
    )
    envelopes = evaluate_municipio(ind)
    rule_ids = [e.rule_id for e in envelopes]
    assert "arrecadacao_critica" in rule_ids


def test_arrecadacao_critica_nao_dispara_se_emprego_ok():
    ind = MunicipioIndicadores(
        cod_ibge=COD_IBGE,
        referencia=REF,
        delta_arrecadacao_yoy=-0.25,  # < -20%
        delta_emprego_yoy=0.05,       # positivo
    )
    envelopes = evaluate_municipio(ind)
    assert not any(e.rule_id == "arrecadacao_critica" for e in envelopes)


def test_arrecadacao_critica_nao_dispara_sem_dados():
    ind = MunicipioIndicadores(
        cod_ibge=COD_IBGE,
        referencia=REF,
        delta_arrecadacao_yoy=None,
        delta_emprego_yoy=None,
    )
    envelopes = evaluate_municipio(ind)
    assert not any(e.rule_id == "arrecadacao_critica" for e in envelopes)


def test_arrecadacao_critica_severity_critical():
    ind = MunicipioIndicadores(
        cod_ibge=COD_IBGE,
        referencia=REF,
        delta_arrecadacao_yoy=-0.30,
        delta_emprego_yoy=-0.20,
    )
    envelopes = evaluate_municipio(ind)
    e = next(ev for ev in envelopes if ev.rule_id == "arrecadacao_critica")
    assert e.severity == Severity.CRITICAL


def test_arrecadacao_critica_envelope_sem_pii():
    ind = MunicipioIndicadores(
        cod_ibge=COD_IBGE,
        referencia=REF,
        delta_arrecadacao_yoy=-0.25,
        delta_emprego_yoy=-0.15,
    )
    envelopes = evaluate_municipio(ind)
    e = next(ev for ev in envelopes if ev.rule_id == "arrecadacao_critica")
    # subject_ref só contém referência não-PII
    assert "municipio_ibge" in e.subject_ref
    assert all(isinstance(v, str) for v in e.subject_ref.values())


def test_arrecadacao_critica_dedup_key_formato():
    ind = MunicipioIndicadores(
        cod_ibge=COD_IBGE,
        referencia=REF,
        delta_arrecadacao_yoy=-0.25,
        delta_emprego_yoy=-0.15,
    )
    envelopes = evaluate_municipio(ind)
    e = next(ev for ev in envelopes if ev.rule_id == "arrecadacao_critica")
    assert e.dedup_key == f"arrecadacao_critica:{COD_IBGE}:{REF}"


# ---------------------------------------------------------------------------
# evaluate_municipio — regra saneamento_baixo
# ---------------------------------------------------------------------------

def test_saneamento_baixo_dispara():
    ind = MunicipioIndicadores(
        cod_ibge=COD_IBGE,
        referencia=REF,
        cobertura_agua_pct=40.0,   # < 50%
        cobertura_esgoto_pct=20.0, # < 30%
    )
    envelopes = evaluate_municipio(ind)
    assert any(e.rule_id == "saneamento_baixo" for e in envelopes)


def test_saneamento_baixo_nao_dispara_agua_ok():
    ind = MunicipioIndicadores(
        cod_ibge=COD_IBGE,
        referencia=REF,
        cobertura_agua_pct=70.0,
        cobertura_esgoto_pct=20.0,
    )
    envelopes = evaluate_municipio(ind)
    assert not any(e.rule_id == "saneamento_baixo" for e in envelopes)


def test_saneamento_baixo_nao_dispara_sem_dados():
    ind = MunicipioIndicadores(
        cod_ibge=COD_IBGE,
        referencia=REF,
        cobertura_agua_pct=None,
        cobertura_esgoto_pct=None,
    )
    envelopes = evaluate_municipio(ind)
    assert not any(e.rule_id == "saneamento_baixo" for e in envelopes)


def test_saneamento_severity_high():
    ind = MunicipioIndicadores(
        cod_ibge=COD_IBGE,
        referencia=REF,
        cobertura_agua_pct=30.0,
        cobertura_esgoto_pct=10.0,
    )
    envelopes = evaluate_municipio(ind)
    e = next(ev for ev in envelopes if ev.rule_id == "saneamento_baixo")
    assert e.severity == Severity.HIGH


# ---------------------------------------------------------------------------
# evaluate_municipio — múltiplas regras ao mesmo tempo
# ---------------------------------------------------------------------------

def test_multiplas_regras_disparam():
    ind = MunicipioIndicadores(
        cod_ibge=COD_IBGE,
        referencia=REF,
        delta_arrecadacao_yoy=-0.30,
        delta_emprego_yoy=-0.20,
        cobertura_agua_pct=40.0,
        cobertura_esgoto_pct=20.0,
    )
    envelopes = evaluate_municipio(ind)
    rule_ids = [e.rule_id for e in envelopes]
    assert "arrecadacao_critica" in rule_ids
    assert "saneamento_baixo" in rule_ids


def test_nenhuma_regra_dispara_dados_bons():
    ind = MunicipioIndicadores(
        cod_ibge=COD_IBGE,
        referencia=REF,
        delta_arrecadacao_yoy=0.05,
        delta_emprego_yoy=0.02,
        cobertura_agua_pct=95.0,
        cobertura_esgoto_pct=85.0,
    )
    envelopes = evaluate_municipio(ind)
    assert envelopes == []


def test_envelopes_sao_alertenvelope():
    ind = MunicipioIndicadores(
        cod_ibge=COD_IBGE,
        referencia=REF,
        delta_arrecadacao_yoy=-0.25,
        delta_emprego_yoy=-0.15,
    )
    envelopes = evaluate_municipio(ind)
    for e in envelopes:
        assert isinstance(e, AlertEnvelope)


# ---------------------------------------------------------------------------
# build_indicadores_from_cache
# ---------------------------------------------------------------------------

def test_build_com_todos_os_dados():
    siconfi_atual = {"valor": 12_000_000.0}
    siconfi_ant = {"valor": 10_000_000.0}
    caged_atual = {"saldo_admissoes_desligamentos": 50}
    caged_ant = {"saldo_admissoes_desligamentos": 100}
    snis = {"cobertura_agua_pct": 45.0, "cobertura_esgoto_pct": 25.0, "lag_days": 548}

    ind = build_indicadores_from_cache(
        cod_ibge=COD_IBGE,
        referencia=REF,
        siconfi_atual=siconfi_atual,
        siconfi_anterior=siconfi_ant,
        caged_atual=caged_atual,
        caged_anterior=caged_ant,
        snis=snis,
    )
    assert ind.delta_arrecadacao_yoy == pytest.approx(0.20, abs=0.001)
    assert ind.delta_emprego_yoy == pytest.approx(-0.50, abs=0.001)
    assert ind.cobertura_agua_pct == 45.0
    assert ind.cobertura_esgoto_pct == 25.0
    assert ind.source_lag_days == 548
    assert ind.sources_missing == []


def test_build_sem_dados_publicos():
    ind = build_indicadores_from_cache(
        cod_ibge=COD_IBGE,
        referencia=REF,
        siconfi_atual=None,
        siconfi_anterior=None,
        caged_atual=None,
        caged_anterior=None,
        snis=None,
    )
    assert ind.delta_arrecadacao_yoy is None
    assert ind.delta_emprego_yoy is None
    assert ind.cobertura_agua_pct is None
    assert "SICONFI" in (ind.sources_missing or [])
    assert "CAGED" in (ind.sources_missing or [])
    assert "SNIS" in (ind.sources_missing or [])


def test_build_delta_arrecadacao_negativo():
    siconfi_atual = {"valor": 7_000_000.0}
    siconfi_ant = {"valor": 10_000_000.0}

    ind = build_indicadores_from_cache(
        cod_ibge=COD_IBGE,
        referencia=REF,
        siconfi_atual=siconfi_atual,
        siconfi_anterior=siconfi_ant,
        caged_atual=None,
        caged_anterior=None,
        snis=None,
    )
    assert ind.delta_arrecadacao_yoy == pytest.approx(-0.30, abs=0.001)


def test_build_siconfi_anterior_zero_sem_delta():
    ind = build_indicadores_from_cache(
        cod_ibge=COD_IBGE,
        referencia=REF,
        siconfi_atual={"valor": 1_000_000.0},
        siconfi_anterior={"valor": 0.0},
        caged_atual=None,
        caged_anterior=None,
        snis=None,
    )
    assert ind.delta_arrecadacao_yoy is None


def test_build_indicadores_campos():
    ind = build_indicadores_from_cache(
        cod_ibge=COD_IBGE,
        referencia=REF,
        siconfi_atual=None,
        siconfi_anterior=None,
        caged_atual=None,
        caged_anterior=None,
        snis=None,
    )
    assert ind.cod_ibge == COD_IBGE
    assert ind.referencia == REF
