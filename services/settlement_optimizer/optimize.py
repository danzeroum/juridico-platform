"""
Núcleo puro do Settlement Optimizer (produto Settlement Optimizer).

Estende a lógica da ConciliaIA com uma análise de decisão explícita: calcula os
valores esperados de continuar o litígio para autor e réu e a Zona de Possível
Acordo (ZOPA). Sem I/O — testável.

Modelo (valor presente simplificado, sem desconto temporal):
  EV_autor = p·V − custo_autor          (o que o autor espera ganhar indo até o fim)
  EV_reu   = p·V + custo_reu            (o que o réu espera perder indo até o fim)

Onde p = probabilidade de procedência (blend TaxPredict + base rate jurimétrica),
V = valor da causa. Há ZOPA quando EV_reu ≥ EV_autor: qualquer acordo em
[EV_autor, EV_reu] é racional para ambos. Heurística — rotulada como tal.
"""
from __future__ import annotations

from typing import Any


def _blend_prob(prob_favorable: float | None, pct_provimento: float | None) -> float:
    """Combina a P(procedência) do modelo com a base rate jurimétrica."""
    sinais = [x for x in (prob_favorable, pct_provimento) if x is not None]
    if not sinais:
        return 0.5  # sem sinal → indiferente
    return max(0.0, min(1.0, sum(sinais) / len(sinais)))


def optimize_settlement(
    valor_causa: float,
    prob_favorable: float | None = None,
    pct_provimento: float | None = None,
    custo_autor: float = 0.0,
    custo_reu: float = 0.0,
) -> dict[str, Any]:
    """Faixa ótima de acordo e recomendação a partir da análise de decisão."""
    if valor_causa < 0:
        raise ValueError("valor_causa não pode ser negativo")

    p = _blend_prob(prob_favorable, pct_provimento)
    ev_autor = p * valor_causa - custo_autor
    ev_reu = p * valor_causa + custo_reu

    tem_zopa = ev_reu >= ev_autor
    piso = max(0.0, ev_autor)
    teto = min(valor_causa, ev_reu)
    ponto_meio = round((piso + teto) / 2, 2) if tem_zopa else None

    return {
        "prob_procedencia": round(p, 4),
        "valor_esperado_autor": round(ev_autor, 2),
        "valor_esperado_reu": round(ev_reu, 2),
        "tem_zopa": tem_zopa,
        "faixa_acordo": [round(piso, 2), round(teto, 2)] if tem_zopa else None,
        "acordo_sugerido": ponto_meio,
        "recomendacao": (
            "ACORDAR" if tem_zopa and ponto_meio is not None else "LITIGAR"
        ),
        "disclaimer": "heurística de análise de decisão — não validada contra desfechos reais",
    }
