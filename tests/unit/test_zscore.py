"""Testes da análise Z-score."""
from __future__ import annotations

import pytest

from services.audit.zscore import ZScoreResult, compute_zscore

# ---------------------------------------------------------------------------
# Validação de entrada
# ---------------------------------------------------------------------------

def test_menos_de_2_valores_levanta_erro():
    with pytest.raises(ValueError, match="2"):
        compute_zscore([1.0])


def test_lista_vazia_levanta_erro():
    with pytest.raises(ValueError, match="2"):
        compute_zscore([])


def test_so_nones_levanta_erro():
    with pytest.raises(ValueError, match="2"):
        compute_zscore([None, None])


# ---------------------------------------------------------------------------
# Cálculo correto
# ---------------------------------------------------------------------------

def test_sem_outliers_distribuicao_normal():
    values = [10.0, 11.0, 9.0, 10.5, 9.5, 10.2, 10.1]
    result = compute_zscore(values, column="despesas", threshold=3.0)
    assert result.outliers == []
    assert result.n_values == 7
    assert 9.0 < result.mean < 11.0


def test_outlier_extremo_detectado():
    # Precisa de amostra grande o suficiente para o outlier não inflar mean/std
    values = [10.0] * 20 + [1000.0]
    result = compute_zscore(values, column="despesas")
    assert len(result.outliers) == 1
    assert result.outliers[0]["value"] == 1000.0
    assert result.outliers[0]["zscore"] > 3.0


def test_negativo_extremo_detectado():
    values = [10.0] * 20 + [-1000.0]
    result = compute_zscore(values, column="receitas")
    assert len(result.outliers) == 1
    assert result.outliers[0]["zscore"] < -3.0


def test_serie_constante_sem_outliers():
    """Desvio padrão zero — nenhum outlier, sem divisão por zero."""
    values = [5.0, 5.0, 5.0, 5.0, 5.0]
    result = compute_zscore(values, column="constante")
    assert result.std == 0.0
    assert result.outliers == []


def test_none_ignorado_no_calculo():
    """Valores None não entram no cálculo."""
    values = [10.0, None, 11.0, None, 9.0]
    result = compute_zscore(values, column="com_none")
    assert result.n_values == 3
    assert abs(result.mean - 10.0) < 0.1


def test_nan_ignorado_no_calculo():
    values = [10.0, float("nan"), 11.0, 9.0]
    result = compute_zscore(values, column="com_nan")
    assert result.n_values == 3


def test_campos_resultado():
    values = [1.0, 2.0, 3.0, 100.0]
    result = compute_zscore(values, column="test", threshold=2.0)
    assert isinstance(result, ZScoreResult)
    assert result.column == "test"
    assert result.threshold == 2.0
    assert isinstance(result.mean, float)
    assert isinstance(result.std, float)
    assert isinstance(result.outliers, list)


def test_threshold_customizado():
    """Threshold menor detecta mais outliers."""
    values = [10.0, 11.0, 10.5, 9.5, 50.0]
    result_default = compute_zscore(values, threshold=3.0)
    result_strict = compute_zscore(values, threshold=1.5)
    assert len(result_strict.outliers) >= len(result_default.outliers)


def test_indice_preservado():
    """O índice no dict de outlier deve corresponder à posição original na lista."""
    values = [10.0] * 15 + [1000.0]
    result = compute_zscore(values)
    assert len(result.outliers) >= 1
    assert result.outliers[0]["index"] == 15


def test_zscore_arredondado():
    values = [1.0, 2.0, 3.0, 100.0]
    result = compute_zscore(values)
    for outlier in result.outliers:
        # zscore deve ter 4 casas decimais
        z = outlier["zscore"]
        assert z == round(z, 4)
