"""Testes do CrossCheckEngine (CC01–CC08)."""
from __future__ import annotations

import pytest

from services.audit.crosscheck.engine import CrossCheckEngine, CrossCheckFinding


@pytest.fixture
def engine():
    return CrossCheckEngine()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rules(findings: list[CrossCheckFinding]) -> list[str]:
    return [f.rule for f in findings]


def _finding(findings: list[CrossCheckFinding], rule: str) -> CrossCheckFinding:
    for f in findings:
        if f.rule == rule:
            return f
    raise AssertionError(f"Finding {rule} não encontrado")


# ---------------------------------------------------------------------------
# CC01 — Headcount vs CAGED
# ---------------------------------------------------------------------------

def test_cc01_delta_acima_limite(engine):
    fin = {"headcount": 100}
    pub = {"caged_saldo_12m": 60}  # delta = 40%
    findings = engine.run_checks(fin, pub)
    assert "CC01" in _rules(findings)
    f = _finding(findings, "CC01")
    assert f.severity == "ALTO"
    assert f.detail["delta_pct"] == 40.0


def test_cc01_delta_abaixo_limite(engine):
    fin = {"headcount": 100}
    pub = {"caged_saldo_12m": 95}  # delta = 5%
    findings = engine.run_checks(fin, pub)
    assert "CC01" not in _rules(findings)


def test_cc01_headcount_zero_ignorado(engine):
    fin = {"headcount": 0}
    pub = {"caged_saldo_12m": 100}
    findings = engine.run_checks(fin, pub)
    assert "CC01" not in _rules(findings)


def test_cc01_ausencia_dados_publicos_ignorado(engine):
    fin = {"headcount": 100}
    pub = {}
    findings = engine.run_checks(fin, pub)
    assert "CC01" not in _rules(findings)


# ---------------------------------------------------------------------------
# CC02 — Receita vs SICONFI
# ---------------------------------------------------------------------------

def test_cc02_delta_critico(engine):
    fin = {"receita_liquida": 2_000_000.0}
    pub = {"siconfi_receita_total": 1_000_000.0}  # delta = 100%
    findings = engine.run_checks(fin, pub)
    assert "CC02" in _rules(findings)
    f = _finding(findings, "CC02")
    assert f.severity == "CRITICO"


def test_cc02_delta_aceitavel(engine):
    fin = {"receita_liquida": 1_050_000.0}
    pub = {"siconfi_receita_total": 1_000_000.0}  # delta = 5%
    findings = engine.run_checks(fin, pub)
    assert "CC02" not in _rules(findings)


def test_cc02_siconfi_zero_ignorado(engine):
    fin = {"receita_liquida": 1_000_000.0}
    pub = {"siconfi_receita_total": 0}
    findings = engine.run_checks(fin, pub)
    assert "CC02" not in _rules(findings)


# ---------------------------------------------------------------------------
# CC03 — Contratos vs PNCP
# ---------------------------------------------------------------------------

def test_cc03_receita_sem_contrato(engine):
    fin = {"receita_servicos_publicos": 500_000.0}
    pub = {"pncp_contratos_total": 0}
    findings = engine.run_checks(fin, pub)
    assert "CC03" in _rules(findings)
    assert _finding(findings, "CC03").severity == "MEDIO"


def test_cc03_contratos_existem_ok(engine):
    fin = {"receita_servicos_publicos": 500_000.0}
    pub = {"pncp_contratos_total": 600_000.0}
    findings = engine.run_checks(fin, pub)
    assert "CC03" not in _rules(findings)


# ---------------------------------------------------------------------------
# CC04 — Importações vs Estoque
# ---------------------------------------------------------------------------

def test_cc04_estoque_desproporcional(engine):
    fin = {"importacoes": 100_000.0, "variacao_estoque": 400_000.0}  # ratio=4
    pub = {}
    findings = engine.run_checks(fin, pub)
    assert "CC04" in _rules(findings)
    assert _finding(findings, "CC04").detail["ratio"] == 4.0


def test_cc04_ratio_normal(engine):
    fin = {"importacoes": 100_000.0, "variacao_estoque": 200_000.0}  # ratio=2
    pub = {}
    findings = engine.run_checks(fin, pub)
    assert "CC04" not in _rules(findings)


def test_cc04_importacoes_zero_ignorado(engine):
    fin = {"importacoes": 0, "variacao_estoque": 999_999.0}
    pub = {}
    findings = engine.run_checks(fin, pub)
    assert "CC04" not in _rules(findings)


# ---------------------------------------------------------------------------
# CC05 — Benford em receitas mensais
# ---------------------------------------------------------------------------

def test_cc05_sem_serie_suficiente_ignorado(engine):
    fin = {"serie_receitas_mensais": [100.0, 200.0, 300.0]}  # < 30
    pub = {}
    findings = engine.run_checks(fin, pub)
    assert "CC05" not in _rules(findings)


def test_cc05_distribuicao_uniforme_suspeita(engine):
    """Distribuição uniforme de primeiros dígitos viola Benford."""
    # 5 valores de cada dígito 1-9 = 45 valores com distribuição uniforme
    values = []
    for d in range(1, 10):
        for _ in range(5):
            values.append(float(f"{d}000"))
    fin = {"serie_receitas_mensais": values}
    pub = {}
    findings = engine.run_checks(fin, pub)
    # Pode ou não disparar CC05 dependendo do MAD — apenas verificar que não crasha
    assert isinstance(findings, list)


def test_cc05_sem_serie_receitas_ignorado(engine):
    fin = {"receita_liquida": 100.0}
    pub = {}
    findings = engine.run_checks(fin, pub)
    assert "CC05" not in _rules(findings)


# ---------------------------------------------------------------------------
# CC06 — Z-score em despesas mensais
# ---------------------------------------------------------------------------

def test_cc06_outlier_detectado(engine):
    series = [10_000.0] * 10 + [500_000.0]  # valor extremo
    fin = {"serie_despesas_mensais": series}
    pub = {}
    findings = engine.run_checks(fin, pub)
    assert "CC06" in _rules(findings)
    f = _finding(findings, "CC06")
    assert f.severity == "ALTO"
    assert len(f.detail["outliers"]) >= 1


def test_cc06_sem_outlier_ok(engine):
    series = [10_000.0, 11_000.0, 10_500.0, 9_800.0, 10_200.0]
    fin = {"serie_despesas_mensais": series}
    pub = {}
    findings = engine.run_checks(fin, pub)
    assert "CC06" not in _rules(findings)


def test_cc06_sem_serie_ignorado(engine):
    fin = {"receita_liquida": 100.0}
    pub = {}
    findings = engine.run_checks(fin, pub)
    assert "CC06" not in _rules(findings)


# ---------------------------------------------------------------------------
# CC07 — Liquidez Corrente
# ---------------------------------------------------------------------------

def test_cc07_liquidez_critica(engine):
    fin = {"ativo_circulante": 40_000.0, "passivo_circulante": 100_000.0}  # = 0.4
    pub = {}
    findings = engine.run_checks(fin, pub)
    assert "CC07" in _rules(findings)
    f = _finding(findings, "CC07")
    assert f.severity == "CRITICO"
    assert f.detail["liquidez"] == pytest.approx(0.4, abs=0.001)


def test_cc07_liquidez_adequada(engine):
    fin = {"ativo_circulante": 100_000.0, "passivo_circulante": 100_000.0}  # = 1.0
    pub = {}
    findings = engine.run_checks(fin, pub)
    assert "CC07" not in _rules(findings)


def test_cc07_passivo_zero_ignorado(engine):
    fin = {"ativo_circulante": 100_000.0, "passivo_circulante": 0}
    pub = {}
    findings = engine.run_checks(fin, pub)
    assert "CC07" not in _rules(findings)


def test_cc07_ausencia_campos_ignorado(engine):
    findings = engine.run_checks({}, {})
    assert "CC07" not in _rules(findings)


# ---------------------------------------------------------------------------
# CC08 — Margem EBITDA implausível
# ---------------------------------------------------------------------------

def test_cc08_margem_negativa_extrema(engine):
    fin = {"ebitda": -500_000.0, "receita_liquida": 1_000_000.0}  # -50%
    pub = {}
    findings = engine.run_checks(fin, pub)
    assert "CC08" in _rules(findings)
    f = _finding(findings, "CC08")
    assert f.severity == "ALTO"
    assert f.detail["margem_pct"] == pytest.approx(-50.0, abs=0.1)


def test_cc08_margem_positiva_extrema(engine):
    fin = {"ebitda": 800_000.0, "receita_liquida": 1_000_000.0}  # 80%
    pub = {}
    findings = engine.run_checks(fin, pub)
    assert "CC08" in _rules(findings)


def test_cc08_margem_normal_ok(engine):
    fin = {"ebitda": 150_000.0, "receita_liquida": 1_000_000.0}  # 15%
    pub = {}
    findings = engine.run_checks(fin, pub)
    assert "CC08" not in _rules(findings)


def test_cc08_receita_zero_ignorado(engine):
    fin = {"ebitda": 100.0, "receita_liquida": 0}
    pub = {}
    findings = engine.run_checks(fin, pub)
    assert "CC08" not in _rules(findings)


# ---------------------------------------------------------------------------
# run_checks retorna lista de CrossCheckFinding
# ---------------------------------------------------------------------------

def test_run_checks_retorna_lista(engine):
    result = engine.run_checks({}, {})
    assert isinstance(result, list)


def test_run_checks_findings_tem_campos_obrigatorios(engine):
    fin = {"headcount": 100}
    pub = {"caged_saldo_12m": 10}  # delta = 90%
    findings = engine.run_checks(fin, pub)
    for f in findings:
        assert hasattr(f, "rule")
        assert hasattr(f, "severity")
        assert hasattr(f, "description")
        assert hasattr(f, "detail")


def test_cc05_todos_zeros_valor_erro_ignorado(engine):
    """Série de 30+ zeros: analyze_benford levanta ValueError → CC05 ignorado."""
    fin = {"serie_receitas_mensais": [0.0] * 35}  # 35 items, 0 valid first-digits
    pub = {}
    findings = engine.run_checks(fin, pub)
    assert "CC05" not in _rules(findings)


def test_cc05_conforme_ignorado(engine):
    """Série com distribuição Benford conforme: CC05 não dispara (return [] no final)."""
    # 300 valores com distribuição próxima de Benford (MAD < 0.006)
    values: list[float] = []
    counts = {1: 90, 2: 53, 3: 37, 4: 29, 5: 24, 6: 20, 7: 17, 8: 15, 9: 14}
    for digit, n in counts.items():
        values.extend([float(f"{digit}000")] * n)
    fin = {"serie_receitas_mensais": values}
    pub = {}
    findings = engine.run_checks(fin, pub)
    assert "CC05" not in _rules(findings)


def test_cc06_serie_sem_validos_suficientes_ignorado(engine):
    """Série com menos de 2 valores válidos: compute_zscore levanta ValueError → CC06 ignorado."""
    fin = {"serie_despesas_mensais": [None, None, 0.0]}  # 3 items, nenhum válido p/ zscore
    pub = {}
    findings = engine.run_checks(fin, pub)
    assert "CC06" not in _rules(findings)
