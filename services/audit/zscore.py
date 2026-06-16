"""
Detecção de outliers por Z-score em demonstrações financeiras.

Identifica entradas que desviam significativamente da média (|z| > threshold).
Threshold padrão: 3.0 (regra dos três sigmas).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class ZScoreResult:
    column: str
    n_values: int
    mean: float
    std: float
    outliers: list[dict] = field(default_factory=list)
    threshold: float = 3.0


def compute_zscore(
    values: list[float | None],
    column: str = "",
    threshold: float = 3.0,
) -> ZScoreResult:
    """
    Calcula Z-scores e retorna entradas com |z| > threshold.

    Valores None e NaN são ignorados no cálculo.
    Se std == 0 (série constante), nenhum outlier é reportado.
    """
    indexed = [(i, v) for i, v in enumerate(values) if v is not None and not math.isnan(v)]
    n = len(indexed)
    if n < 2:
        raise ValueError(f"Z-score requer ao menos 2 valores; recebido {n} em '{column}'")

    vals = [v for _, v in indexed]
    mean = sum(vals) / n
    variance = sum((v - mean) ** 2 for v in vals) / n
    std = math.sqrt(variance)

    outliers: list[dict] = []
    if std > 0:
        for idx, v in indexed:
            z = (v - mean) / std
            if abs(z) > threshold:
                outliers.append({"index": idx, "value": v, "zscore": round(z, 4)})

    return ZScoreResult(
        column=column,
        n_values=n,
        mean=round(mean, 4),
        std=round(std, 4),
        outliers=outliers,
        threshold=threshold,
    )
