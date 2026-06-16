"""
Validação e métricas do modelo LegalScore.

O score é rotulado como HEURÍSTICA até que:
1. Um dataset de desfechos reais seja coletado (Fase 1d: t+6 meses de dados)
2. AUC ≥ 0.70 e Brier score ≤ 0.20 sejam alcançados
3. Calibração (reliability diagram) mostre boa correspondência

Estrutura esperada do dataset de validação:
    cnpj: str
    score_previsto: int           (0–1000)
    desfecho_real: int            (1=falência/recuperação judicial, 0=regular)
    data_desfecho: str            (YYYY-MM-DD)
    data_score: str               (YYYY-MM-DD do score calculado)

Métricas SMART (Seção 1.4 do ROADMAP):
    Específica:  AUC-ROC ≥ 0.70 em holdout 20% (por setor CNAE)
    Mensurável:  Brier score ≤ 0.20 (calibração preditiva)
    Alcançável:  baseline logístico simples atinge ~0.65 com 3 features
    Relevante:   mede real capacidade discriminativa, não acurácia em threshold
    Temporal:    6 meses de dados; reavaliação anual (drift de modelo)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelMetrics:
    model_type: str = "heuristica"
    auc: float | None = None
    brier_score: float | None = None
    calibration_r2: float | None = None
    n_validation_samples: int | None = None
    validation_status: str = "pending"
    validation_note: str = (
        "Score é heurística baseada em MLR por CNAE. "
        "Aguardando dataset de desfechos reais (t+6 meses) para calcular "
        "AUC-ROC e Brier score e promover a 'validado'."
    )
    last_calibrated: str | None = None
    target_auc: float = 0.70
    target_brier: float = 0.20


def get_current_metrics() -> ModelMetrics:
    """Retorna métricas atuais do modelo. Pendente até dataset de desfechos disponível."""
    return ModelMetrics()


def compute_auc(y_true: list[int], scores: list[int]) -> float:
    """
    Calcula AUC-ROC (área sob a curva ROC) manualmente.

    Complexidade: O(n²) — adequado para datasets de validação (<10k amostras).
    Para datasets maiores, usar scikit-learn.
    """
    n = len(y_true)
    if n == 0:
        raise ValueError("Lista vazia")
    if len(scores) != n:
        raise ValueError("y_true e scores devem ter o mesmo tamanho")

    positives = sum(y_true)
    negatives = n - positives
    if positives == 0 or negatives == 0:
        raise ValueError("Necessário ao menos uma amostra positiva e uma negativa")

    # Ordenar por score decrescente
    pairs = sorted(zip(scores, y_true, strict=False), reverse=True)

    tp = 0.0
    fp = 0.0
    prev_fp = 0.0
    auc = 0.0

    for _, label in pairs:
        if label == 1:
            tp += 1
        else:
            fp += 1
            auc += tp * (fp - prev_fp)
            prev_fp = fp

    auc /= positives * negatives
    return round(auc, 4)


def compute_brier(y_true: list[int], probabilities: list[float]) -> float:
    """
    Calcula Brier score: média de (probabilidade - desfecho)².

    Score perfeito = 0.0; score aleatório ≈ 0.25.
    Threshold alvo: ≤ 0.20.
    """
    if len(y_true) != len(probabilities):
        raise ValueError("y_true e probabilities devem ter o mesmo tamanho")
    if not y_true:
        raise ValueError("Lista vazia")
    n = len(y_true)
    return round(sum((p - y) ** 2 for y, p in zip(y_true, probabilities, strict=False)) / n, 4)


def score_to_probability(score: int) -> float:
    """Converte score [0-1000] para probabilidade de risco (0-1)."""
    return 1.0 - score / 1000.0
