"""
ConciliaIA — recomendação de faixa de acordo.

Combina prior histórico por tipo de ação com ajustes de:
  - Probabilidade de procedência (TaxPredict, opcional)
  - Risco do réu (LegalScore, opcional)
"""
from __future__ import annotations

from datetime import UTC, datetime

from services.shared.contracts.concilia import ConciliaFator, ConciliaRequest, ConciliaResponse

# Prior histórico de percentual de acordo por tipo de ação
_BASE_PCT: dict[str, float] = {
    "TRABALHISTA":    0.55,
    "CIVEL":          0.45,
    "TRIBUTARIO":     0.35,
    "PREVIDENCIARIO": 0.65,
    "ADMINISTRATIVO": 0.40,
    "CONSUMERISTA":   0.50,
}

_PCT_NEUTRO  = 0.45  # referência para cálculo de impacto relativo
_CI_SPREAD   = 0.30  # valor_min = sugerido * 0.70; valor_max = sugerido * 1.30 (≤ causa)
_PCT_MIN     = 0.05
_PCT_MAX     = 0.95


def recommend_settlement(
    request: ConciliaRequest,
    probability_favorable: float | None = None,
    risk_score_reu: int | None = None,
) -> ConciliaResponse:
    """
    Recomenda faixa de acordo.

    Args:
        request: dados da ação
        probability_favorable: P(procedência) do TaxPredict (0.0–1.0)
        risk_score_reu: LegalScore do réu (0–1000)

    Returns:
        ConciliaResponse com valor_minimo, valor_sugerido, valor_maximo e fatores
    """
    tipo = request.tipo_acao.value
    base_pct = _BASE_PCT.get(tipo, _PCT_NEUTRO)
    fatores: list[ConciliaFator] = [
        ConciliaFator(
            nome="Prior histórico",
            impacto=round(base_pct - _PCT_NEUTRO, 3),
            descricao=f"Percentual histórico de acordo para ações {tipo}: {base_pct:.0%}",
        )
    ]

    pct = base_pct

    # Ajuste por probabilidade de procedência (TaxPredict)
    if probability_favorable is not None:
        delta = (probability_favorable - base_pct) * 0.5  # ajuste parcial
        pct += delta
        fatores.append(ConciliaFator(
            nome="Probabilidade de procedência",
            impacto=round(delta, 3),
            descricao=f"TaxPredict P(favorável)={probability_favorable:.1%} → {delta:+.1%}",
        ))

    # Ajuste por risco do réu (LegalScore)
    if risk_score_reu is not None:
        risk_norm = risk_score_reu / 1000.0
        risk_delta = (risk_norm - 0.5) * 0.10  # ±5%
        pct += risk_delta
        fatores.append(ConciliaFator(
            nome="Risco do réu (LegalScore)",
            impacto=round(risk_delta, 3),
            descricao=f"LegalScore={risk_score_reu}/1000 → {risk_delta:+.1%}",
        ))

    pct = max(_PCT_MIN, min(_PCT_MAX, pct))
    valor_sugerido = request.valor_causa * pct
    valor_minimo   = valor_sugerido * (1 - _CI_SPREAD)
    valor_maximo   = min(request.valor_causa, valor_sugerido * (1 + _CI_SPREAD))

    return ConciliaResponse(
        valor_minimo=round(valor_minimo, 2),
        valor_sugerido=round(valor_sugerido, 2),
        valor_maximo=round(valor_maximo, 2),
        percentual_causa=round(pct, 4),
        fatores=fatores,
        risco_reu=risk_score_reu,
        probabilidade_procedencia=probability_favorable,
        computed_at=datetime.now(UTC).isoformat(),
    )
