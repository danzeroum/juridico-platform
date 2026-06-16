"""Testes da análise de Lei de Benford."""
from __future__ import annotations

import math

import pytest

from services.audit.benford import (
    BENFORD_EXPECTED,
    BenfordResult,
    _first_significant_digit,
    analyze_benford,
)

# ---------------------------------------------------------------------------
# _first_significant_digit
# ---------------------------------------------------------------------------

class TestFirstSignificantDigit:
    def test_integer(self):
        assert _first_significant_digit(123.0) == 1

    def test_small_decimal(self):
        assert _first_significant_digit(0.0047) == 4

    def test_exact_power_ten(self):
        assert _first_significant_digit(1000.0) == 1

    def test_negative(self):
        assert _first_significant_digit(-7.5) == 7

    def test_zero_returns_none(self):
        assert _first_significant_digit(0.0) is None

    def test_nan_returns_none(self):
        assert _first_significant_digit(float("nan")) is None

    def test_inf_returns_none(self):
        assert _first_significant_digit(float("inf")) is None

    def test_digit_9(self):
        assert _first_significant_digit(9.99) == 9

    def test_digit_5(self):
        assert _first_significant_digit(50_000.0) == 5


# ---------------------------------------------------------------------------
# analyze_benford — erros de validação
# ---------------------------------------------------------------------------

def test_benford_menos_de_30_valores_levanta_erro():
    with pytest.raises(ValueError, match="30"):
        analyze_benford([1.0, 2.0, 3.0])


def test_benford_exatamente_30_nao_levanta():
    values = list(range(1, 31))
    result = analyze_benford([float(v) for v in values], column="test")
    assert isinstance(result, BenfordResult)


# ---------------------------------------------------------------------------
# analyze_benford — distribuição perfeita de Benford
# ---------------------------------------------------------------------------

def _generate_benford_data(n: int = 1000) -> list[float]:
    """Gera números que seguem a distribuição de Benford exatamente."""
    import random
    random.seed(42)
    values = []
    for _ in range(n):
        # Usar método de inversão: U ~ Uniform → 10^U tem primeiro dígito Benford
        u = random.uniform(0, 1)
        v = 10 ** u
        values.append(v * random.uniform(1, 100))
    return values


def test_benford_conforme_com_dados_benford():
    values = _generate_benford_data(1000)
    result = analyze_benford(values, column="receitas")
    assert result.status in ("CONFORME", "MARGINAL"), f"Esperado CONFORME/MARGINAL, obtido {result.status}"
    assert result.n_values == 1000
    assert result.mad >= 0


def test_benford_suspeito_com_dados_uniformes():
    """Distribuição uniforme de dígitos viola Benford."""
    values = []
    for d in range(1, 10):
        for _ in range(50):  # 50 de cada dígito = uniforme
            values.append(float(f"{d}00"))
    result = analyze_benford(values, column="suspeito")
    assert result.status in ("MARGINAL", "SUSPEITO"), f"Distribuição uniforme deve ser suspeita: {result.status}"


def test_benford_resultado_campos():
    values = _generate_benford_data(300)
    result = analyze_benford(values, column="col_teste")
    assert result.column == "col_teste"
    assert result.n_values == 300
    assert isinstance(result.observed, dict)
    assert isinstance(result.expected, dict)
    assert set(result.observed.keys()) == set(range(1, 10))
    assert set(result.expected.keys()) == set(range(1, 10))
    assert isinstance(result.deviating_digits, list)


def test_benford_expected_soma_um():
    total = sum(BENFORD_EXPECTED.values())
    assert abs(total - 1.0) < 1e-9, f"Distribuição Benford deve somar 1: {total}"


def test_benford_ignora_zeros_e_none():
    values = [0.0, None, 100.0, 200.0] + [float(i) * 10 for i in range(1, 30)]
    result = analyze_benford(values, column="com_zeros")
    assert result.n_values < len(values)  # zeros e None descartados


def test_benford_mad_entre_zero_e_um():
    values = _generate_benford_data(500)
    result = analyze_benford(values)
    assert 0 <= result.mad <= 1


# ---------------------------------------------------------------------------
# Benford expected values (checagem matemática)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("d,expected", [
    (1, math.log10(2)),      # log10(1 + 1/1) = log10(2) ≈ 0.301
    (9, math.log10(10 / 9)), # log10(1 + 1/9) ≈ 0.046
])
def test_benford_expected_valores_matematicos(d: int, expected: float):
    assert abs(BENFORD_EXPECTED[d] - expected) < 1e-10
