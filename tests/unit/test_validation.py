"""
Testes do módulo de validação do modelo LegalScore.

Cobrem: AUC-ROC, Brier score, conversão score→probabilidade.
"""

import pytest


class TestComputeAUC:
    def _fn(self):
        from services.scoring.validation import compute_auc
        return compute_auc

    def test_perfect_classifier(self):
        compute_auc = self._fn()
        # Scores altos = positivos, scores baixos = negativos
        y_true = [1, 1, 1, 0, 0, 0]
        scores = [900, 850, 800, 300, 200, 100]
        assert compute_auc(y_true, scores) == pytest.approx(1.0)

    def test_half_auc_classifier(self):
        compute_auc = self._fn()
        # Positivo alto, negativo, negativo, positivo baixo → AUC = 0.5 exato
        y_true = [1, 0, 0, 1]
        scores = [800, 700, 400, 300]
        assert compute_auc(y_true, scores) == pytest.approx(0.5)

    def test_inverse_classifier(self):
        compute_auc = self._fn()
        y_true = [1, 1, 0, 0]
        scores = [100, 200, 800, 900]
        # Classificador invertido → AUC ≈ 0.0
        assert compute_auc(y_true, scores) == pytest.approx(0.0)

    def test_empty_raises(self):
        compute_auc = self._fn()
        with pytest.raises(ValueError, match="vazia"):
            compute_auc([], [])

    def test_mismatched_lengths_raises(self):
        compute_auc = self._fn()
        with pytest.raises(ValueError, match="mesmo tamanho"):
            compute_auc([1, 0], [500])

    def test_all_positive_raises(self):
        compute_auc = self._fn()
        with pytest.raises(ValueError, match="negativa"):
            compute_auc([1, 1, 1], [700, 600, 500])

    def test_all_negative_raises(self):
        compute_auc = self._fn()
        with pytest.raises(ValueError, match="positiva"):
            compute_auc([0, 0, 0], [700, 600, 500])

    def test_realistic_scenario(self):
        compute_auc = self._fn()
        # Dataset sintético com AUC esperada ~0.8
        y_true = [1, 1, 1, 1, 1, 0, 0, 0, 0, 0]
        scores = [850, 780, 720, 650, 600, 550, 450, 380, 280, 150]
        auc = compute_auc(y_true, scores)
        assert 0.6 <= auc <= 1.0  # modelo decente


class TestComputeBrier:
    def _fn(self):
        from services.scoring.validation import compute_brier
        return compute_brier

    def test_perfect_prediction(self):
        compute_brier = self._fn()
        y_true = [1, 1, 0, 0]
        probs = [1.0, 1.0, 0.0, 0.0]
        assert compute_brier(y_true, probs) == pytest.approx(0.0)

    def test_random_prediction(self):
        compute_brier = self._fn()
        y_true = [1, 1, 0, 0]
        probs = [0.5, 0.5, 0.5, 0.5]
        assert compute_brier(y_true, probs) == pytest.approx(0.25)

    def test_worst_prediction(self):
        compute_brier = self._fn()
        y_true = [1, 0]
        probs = [0.0, 1.0]  # completamente errado
        assert compute_brier(y_true, probs) == pytest.approx(1.0)

    def test_empty_raises(self):
        compute_brier = self._fn()
        with pytest.raises(ValueError, match="vazia"):
            compute_brier([], [])

    def test_mismatched_raises(self):
        compute_brier = self._fn()
        with pytest.raises(ValueError, match="mesmo tamanho"):
            compute_brier([1, 0], [0.5])


class TestScoreToProbability:
    def _fn(self):
        from services.scoring.validation import score_to_probability
        return score_to_probability

    def test_score_1000_is_zero_risk(self):
        score_to_probability = self._fn()
        assert score_to_probability(1000) == pytest.approx(0.0)

    def test_score_0_is_full_risk(self):
        score_to_probability = self._fn()
        assert score_to_probability(0) == pytest.approx(1.0)

    def test_score_500_is_half_risk(self):
        score_to_probability = self._fn()
        assert score_to_probability(500) == pytest.approx(0.5)

    def test_score_800_is_low_risk(self):
        score_to_probability = self._fn()
        prob = score_to_probability(800)
        assert prob == pytest.approx(0.2)


class TestGetCurrentMetrics:
    def test_returns_pending_status(self):
        from services.scoring.validation import get_current_metrics
        metrics = get_current_metrics()
        assert metrics.validation_status == "pending"
        assert metrics.auc is None
        assert metrics.brier_score is None
        assert metrics.model_type == "heuristica"
        assert metrics.target_auc == 0.70
        assert metrics.target_brier == 0.20
