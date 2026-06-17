"""Testes do LicitaWatch monitor."""
from __future__ import annotations

from services.ingest.contracts.pncp import PncpContratoSilver
from services.licitawatch.monitor import (
    LicitacaoIndicadores,
    build_indicadores_from_silver,
    evaluate_licitacoes,
)
from services.shared.contracts.alerts import AlertEnvelope, Severity

CNPJ = "12345678000195"
REF  = "2023"


def _make_silver(
    numero: str = "001",
    cnpj_fornecedor: str | None = "98765432000110",
    modalidade: str = "PREGAO_ELETRONICO",
    valor: float = 10_000.0,
    is_dispensa: bool = False,
    is_unico: bool = False,
    prazo_dias: int | None = 10,
) -> PncpContratoSilver:
    return PncpContratoSilver(
        numero_controle=numero,
        cnpj_orgao=CNPJ,
        cnpj_fornecedor=cnpj_fornecedor,
        objeto="Objeto de teste",
        modalidade=modalidade,
        valor_contrato=valor,
        valor_log=4.0,
        data_publicacao="2023-01-01",
        prazo_abertura_dias=prazo_dias,
        is_dispensa=is_dispensa,
        is_unico_proponente=is_unico,
        source="PNCP",
        ingested_at="2023-12-01T00:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# LL01 — concentração de fornecedor
# ---------------------------------------------------------------------------

def test_ll01_dispara_alta_concentracao():
    contratos = [_make_silver(numero=str(i), cnpj_fornecedor="11111111000111") for i in range(8)]
    contratos += [_make_silver(numero=str(i + 8), cnpj_fornecedor="22222222000122") for i in range(2)]
    ind = build_indicadores_from_silver(CNPJ, REF, contratos)
    envelopes = evaluate_licitacoes(ind)
    assert any(e.rule_id == "LL01_concentracao_fornecedor" for e in envelopes)


def test_ll01_nao_dispara_distribuido():
    contratos = [_make_silver(numero=str(i), cnpj_fornecedor=f"1111111100011{i}") for i in range(5)]
    ind = build_indicadores_from_silver(CNPJ, REF, contratos)
    envelopes = evaluate_licitacoes(ind)
    assert not any(e.rule_id == "LL01_concentracao_fornecedor" for e in envelopes)


def test_ll01_severity_alto():
    contratos = [_make_silver(numero=str(i), cnpj_fornecedor="11111111000111") for i in range(8)]
    contratos += [_make_silver(numero=str(i + 8), cnpj_fornecedor="22222222000122") for i in range(2)]
    ind = build_indicadores_from_silver(CNPJ, REF, contratos)
    envelopes = evaluate_licitacoes(ind)
    e = next(ev for ev in envelopes if ev.rule_id == "LL01_concentracao_fornecedor")
    assert e.severity == Severity.HIGH


# ---------------------------------------------------------------------------
# LL02 — dispensa excessiva
# ---------------------------------------------------------------------------

def test_ll02_dispara_dispensas_excessivas():
    contratos = [_make_silver(numero=str(i), is_dispensa=True) for i in range(4)]
    contratos += [_make_silver(numero=str(i + 4)) for i in range(6)]
    ind = build_indicadores_from_silver(CNPJ, REF, contratos)
    envelopes = evaluate_licitacoes(ind)
    assert any(e.rule_id == "LL02_dispensa_excessiva" for e in envelopes)


def test_ll02_nao_dispara_poucos():
    contratos = [_make_silver(numero=str(i), is_dispensa=(i == 0)) for i in range(10)]
    ind = build_indicadores_from_silver(CNPJ, REF, contratos)
    envelopes = evaluate_licitacoes(ind)
    assert not any(e.rule_id == "LL02_dispensa_excessiva" for e in envelopes)


# ---------------------------------------------------------------------------
# LL03 — único proponente
# ---------------------------------------------------------------------------

def test_ll03_dispara_unico_proponente():
    contratos = [_make_silver(numero=str(i), is_unico=True) for i in range(6)]
    contratos += [_make_silver(numero=str(i + 6)) for i in range(4)]
    ind = build_indicadores_from_silver(CNPJ, REF, contratos)
    envelopes = evaluate_licitacoes(ind)
    assert any(e.rule_id == "LL03_unico_proponente" for e in envelopes)


def test_ll03_severity_critico():
    contratos = [_make_silver(numero=str(i), is_unico=True) for i in range(6)]
    contratos += [_make_silver(numero=str(i + 6)) for i in range(4)]
    ind = build_indicadores_from_silver(CNPJ, REF, contratos)
    envelopes = evaluate_licitacoes(ind)
    e = next(ev for ev in envelopes if ev.rule_id == "LL03_unico_proponente")
    assert e.severity == Severity.CRITICAL


# ---------------------------------------------------------------------------
# LL04 — prazo curto
# ---------------------------------------------------------------------------

def test_ll04_dispara_prazo_curto():
    contratos = [_make_silver(numero=str(i), prazo_dias=2) for i in range(3)]
    contratos += [_make_silver(numero=str(i + 3)) for i in range(7)]
    ind = build_indicadores_from_silver(CNPJ, REF, contratos)
    envelopes = evaluate_licitacoes(ind)
    assert any(e.rule_id == "LL04_prazo_curto" for e in envelopes)


def test_ll04_nao_dispara_prazo_normal():
    contratos = [_make_silver(numero=str(i), prazo_dias=15) for i in range(10)]
    ind = build_indicadores_from_silver(CNPJ, REF, contratos)
    envelopes = evaluate_licitacoes(ind)
    assert not any(e.rule_id == "LL04_prazo_curto" for e in envelopes)


def test_ll04_ignora_sem_prazo():
    contratos = [_make_silver(numero=str(i), prazo_dias=None) for i in range(5)]
    ind = build_indicadores_from_silver(CNPJ, REF, contratos)
    envelopes = evaluate_licitacoes(ind)
    assert not any(e.rule_id == "LL04_prazo_curto" for e in envelopes)


# ---------------------------------------------------------------------------
# Múltiplas regras e dedup_key
# ---------------------------------------------------------------------------

def test_multiplas_regras_disparam():
    contratos = [_make_silver(numero=str(i), cnpj_fornecedor="11111111000111",
                              is_dispensa=True, is_unico=True, prazo_dias=1) for i in range(5)]
    contratos += [_make_silver(numero=str(i + 5)) for i in range(5)]
    ind = build_indicadores_from_silver(CNPJ, REF, contratos)
    envelopes = evaluate_licitacoes(ind)
    rule_ids = {e.rule_id for e in envelopes}
    assert len(rule_ids) >= 2


def test_nenhuma_regra_dados_saudaveis():
    contratos = [_make_silver(numero=str(i), cnpj_fornecedor=f"1234567800011{i}",
                              is_dispensa=False, is_unico=False, prazo_dias=15) for i in range(10)]
    ind = build_indicadores_from_silver(CNPJ, REF, contratos)
    envelopes = evaluate_licitacoes(ind)
    assert envelopes == []


# ---------------------------------------------------------------------------
# Deduplicação por alert_id determinístico
# ---------------------------------------------------------------------------

def test_alert_id_deterministico_mesmo_orgao_referencia():
    """
    Duas avaliações do mesmo (órgão, referência) produzem o mesmo alert_id.
    ON CONFLICT (alert_id) DO NOTHING garante dedup sem worker extra.
    """
    contratos = [_make_silver(numero=str(i), cnpj_fornecedor="11111111000111") for i in range(8)]
    contratos += [_make_silver(numero=str(i + 8), cnpj_fornecedor="22222222000122") for i in range(2)]
    ind = build_indicadores_from_silver(CNPJ, REF, contratos)
    env1 = {e.rule_id: e.alert_id for e in evaluate_licitacoes(ind)}
    env2 = {e.rule_id: e.alert_id for e in evaluate_licitacoes(ind)}
    assert env1 == env2, "alert_id deve ser determinístico para o mesmo (regra, órgão, referência)"


def test_alert_id_diferente_para_referencia_diferente():
    """Ano diferente → alert_id diferente (re-alertar em novo período é esperado)."""
    contratos = [_make_silver(numero=str(i), cnpj_fornecedor="11111111000111") for i in range(8)]
    contratos += [_make_silver(numero=str(i + 8), cnpj_fornecedor="22222222000122") for i in range(2)]
    ind_2023 = build_indicadores_from_silver(CNPJ, "2023", contratos)
    ind_2024 = build_indicadores_from_silver(CNPJ, "2024", contratos)
    env_2023 = {e.rule_id: e.alert_id for e in evaluate_licitacoes(ind_2023)}
    env_2024 = {e.rule_id: e.alert_id for e in evaluate_licitacoes(ind_2024)}
    for rule_id in env_2023:
        assert env_2023[rule_id] != env_2024[rule_id]


def test_dedup_key_formato():
    ind = LicitacaoIndicadores(
        cnpj_orgao=CNPJ, referencia=REF,
        total_contratos=10, pct_mesmo_vencedor=0.8,
    )
    envelopes = evaluate_licitacoes(ind)
    e = next(ev for ev in envelopes if ev.rule_id == "LL01_concentracao_fornecedor")
    assert e.dedup_key == f"LL01_concentracao_fornecedor:{CNPJ}:{REF}"


def test_envelopes_sao_alertenvelope():
    ind = LicitacaoIndicadores(
        cnpj_orgao=CNPJ, referencia=REF,
        total_contratos=10, pct_dispensa=0.5,
    )
    envelopes = evaluate_licitacoes(ind)
    for e in envelopes:
        assert isinstance(e, AlertEnvelope)


def test_zero_contratos_sem_alertas():
    ind = LicitacaoIndicadores(cnpj_orgao=CNPJ, referencia=REF, total_contratos=0)
    assert evaluate_licitacoes(ind) == []


def test_subject_ref_sem_pii():
    ind = LicitacaoIndicadores(
        cnpj_orgao=CNPJ, referencia=REF,
        total_contratos=10, pct_mesmo_vencedor=0.9,
    )
    envelopes = evaluate_licitacoes(ind)
    e = envelopes[0]
    assert "cnpj" in e.subject_ref
    assert all(isinstance(v, str) for v in e.subject_ref.values())
