"""
Testes do AnomalyDetector.

Garante que o bug do fit/detect está corrigido:
- detect() sem fit() prévio levanta RuntimeError.
- Fallback: threshold comparado com distribuição de treino (não com si mesmo).
"""
import numpy as np
import pytest


@pytest.fixture
def detector():
    from services.audit.anomaly.detector import AnomalyDetector
    return AnomalyDetector(contamination=0.05)


@pytest.fixture
def X_normal():
    """Dados normais centrados em zero."""
    rng = np.random.default_rng(42)
    return rng.normal(loc=0, scale=1, size=(200, 5)).astype(np.float32)


def test_detect_sem_fit_levanta_erro(detector):
    """detect() deve exigir fit() prévio — não falhar silenciosamente."""
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float32)
    with pytest.raises(RuntimeError, match="fit\\(\\)"):
        detector.detect(x)


def test_fit_retorna_self(detector, X_normal):
    result = detector.fit(X_normal)
    assert result is detector


def test_detect_apos_fit_retorna_dict(detector, X_normal):
    detector.fit(X_normal)
    x = X_normal[0]
    result = detector.detect(x)
    assert "anomaly_score" in result
    assert "is_anomaly" in result
    assert "method" in result
    assert isinstance(result["is_anomaly"], bool)
    assert isinstance(result["anomaly_score"], float)


def test_outlier_detectado(detector, X_normal):
    """Um ponto com valores extremos deve ser detectado como anomalia."""
    detector.fit(X_normal)
    outlier = np.array([100.0, 100.0, 100.0, 100.0, 100.0], dtype=np.float32)
    result = detector.detect(outlier)
    assert result["is_anomaly"] is True, "Outlier extremo deve ser detectado"


def test_ponto_normal_nao_anomalia(detector, X_normal):
    """Um ponto dentro da distribuição de treino não deve ser anomalia."""
    detector.fit(X_normal)
    normal_point = np.array([0.1, -0.1, 0.2, -0.2, 0.0], dtype=np.float32)
    result = detector.detect(normal_point)
    assert result["is_anomaly"] is False, "Ponto normal não deve ser anomalia"


def test_metodo_isolation_forest(detector, X_normal):
    """Método padrão deve ser isolation_forest quando fit() funcionou."""
    detector.fit(X_normal)
    x = X_normal[0]
    result = detector.detect(x)
    assert result["method"] == "isolation_forest"


def test_threshold_calculado_no_fit(detector, X_normal):
    """Fallback threshold deve ser calculado no fit(), não em cada detect()."""
    detector.fit(X_normal)
    assert detector._fallback_threshold is not None
    assert isinstance(detector._fallback_threshold, float)
    assert detector._fallback_threshold > 0
