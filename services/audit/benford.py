"""
Análise da Lei de Benford para detecção de anomalias contábeis.

A distribuição de primeiros dígitos de dados financeiros orgânicos segue:
  P(d) = log10(1 + 1/d)  para d em {1, ..., 9}

Thresholds MAD (Mean Absolute Deviation):
  < 0.006   → CONFORME
  0.006–0.012 → MARGINAL (investigar)
  > 0.012   → SUSPEITO (reportar)

Referência: Benford (1938). The Law of Anomalous Numbers.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

BENFORD_EXPECTED: dict[int, float] = {d: math.log10(1 + 1 / d) for d in range(1, 10)}

MAD_CONFORME = 0.006
MAD_SUSPEITO = 0.012
DESVIO_DIGITO_THRESHOLD = 0.015
MIN_VALORES = 30


def _first_significant_digit(value: float) -> int | None:
    """Extrai o primeiro dígito significativo (ignora zeros e NaN)."""
    v = abs(value)
    if v == 0 or math.isnan(v) or math.isinf(v):
        return None
    while v >= 10:
        v /= 10
    while v < 1:
        v *= 10
    return int(v)


@dataclass
class BenfordResult:
    n_values: int
    observed: dict[int, float]
    expected: dict[int, float]
    mad: float
    status: str  # "CONFORME" | "MARGINAL" | "SUSPEITO"
    deviating_digits: list[int] = field(default_factory=list)
    column: str = ""


def analyze_benford(values: list[float], column: str = "") -> BenfordResult:
    """
    Analisa se a distribuição de primeiros dígitos segue a Lei de Benford.

    Requer ao menos 30 valores para confiabilidade estatística.
    Valores zero e None são ignorados.
    """
    digits = [_first_significant_digit(v) for v in values if v is not None]
    digits = [d for d in digits if d is not None]

    n = len(digits)
    if n < MIN_VALORES:
        raise ValueError(f"Benford requer ao menos {MIN_VALORES} valores; recebido {n} em '{column}'")

    counts: dict[int, int] = {d: 0 for d in range(1, 10)}
    for d in digits:
        if 1 <= d <= 9:
            counts[d] += 1

    observed = {d: counts[d] / n for d in range(1, 10)}
    mad = sum(abs(observed[d] - BENFORD_EXPECTED[d]) for d in range(1, 10)) / 9

    if mad < MAD_CONFORME:
        status = "CONFORME"
    elif mad < MAD_SUSPEITO:
        status = "MARGINAL"
    else:
        status = "SUSPEITO"

    deviating = [d for d in range(1, 10) if abs(observed[d] - BENFORD_EXPECTED[d]) > DESVIO_DIGITO_THRESHOLD]

    return BenfordResult(
        n_values=n,
        observed={d: round(observed[d], 6) for d in range(1, 10)},
        expected={d: round(BENFORD_EXPECTED[d], 6) for d in range(1, 10)},
        mad=round(mad, 6),
        status=status,
        deviating_digits=deviating,
        column=column,
    )
