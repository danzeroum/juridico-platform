"""
Núcleo puro de previsão de demanda (produto Demand Forecasting).

Projeta o volume futuro de ações por (tribunal, classe/assunto) a partir da série
histórica de `n_processos` em `jurimetria.indicador`. Sem dependências pesadas:
regressão linear por mínimos quadrados + média móvel, o suficiente para uma
projeção de curto prazo explicável. Sem I/O — testável isoladamente.

Limitações (documentadas): requer ≥ 3 períodos; a ABJ ajuda no cold-start
(backfill histórico). Não modela sazonalidade — projeção de tendência linear com
intervalo heurístico. Rotulado como heurística até validação com desfechos reais.
"""
from __future__ import annotations

from typing import Any

MIN_PERIODOS = 3


def _linear_fit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Ajuste linear y = a + b·x por mínimos quadrados. Retorna (a, b)."""
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        return mean_y, 0.0
    b = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=False)) / denom
    a = mean_y - b * mean_x
    return a, b


def forecast_series(valores: list[float], horizonte: int = 3) -> dict[str, Any]:
    """
    Projeta `horizonte` períodos à frente a partir da série `valores` (ordenada do
    mais antigo ao mais recente).

    Retorna tendência (b), pontos projetados (não-negativos) e um intervalo
    heurístico baseado no desvio residual. `status="insuficiente"` se faltam dados.
    """
    serie = [float(v) for v in valores if v is not None]
    if len(serie) < MIN_PERIODOS:
        return {"status": "insuficiente", "min_periodos": MIN_PERIODOS, "n": len(serie)}

    xs = [float(i) for i in range(len(serie))]
    a, b = _linear_fit(xs, serie)

    # Desvio residual (proxy de incerteza) para o intervalo.
    resid = [serie[i] - (a + b * xs[i]) for i in range(len(serie))]
    rmse = (sum(r * r for r in resid) / len(resid)) ** 0.5

    projecoes: list[dict[str, Any]] = []
    for h in range(1, horizonte + 1):
        x = len(serie) - 1 + h
        ponto = max(0.0, a + b * x)
        margem = 1.96 * rmse
        projecoes.append({
            "passo": h,
            "valor": round(ponto, 2),
            "intervalo": [round(max(0.0, ponto - margem), 2), round(ponto + margem, 2)],
        })

    tendencia = "CRESCENTE" if b > 0 else ("DECRESCENTE" if b < 0 else "ESTAVEL")
    return {
        "status": "ok",
        "tendencia": tendencia,
        "inclinacao": round(b, 4),
        "ultimo_valor": round(serie[-1], 2),
        "projecoes": projecoes,
        "disclaimer": "heurística (tendência linear) — não validada contra desfechos reais",
    }
