"""Testes do núcleo puro de previsão de demanda (services/forecasting/forecast.py)."""
from services.forecasting import forecast


def test_serie_insuficiente():
    r = forecast.forecast_series([10, 20], horizonte=3)
    assert r["status"] == "insuficiente"


def test_tendencia_crescente_projeta_acima_do_ultimo():
    r = forecast.forecast_series([10, 20, 30, 40], horizonte=2)
    assert r["status"] == "ok"
    assert r["tendencia"] == "CRESCENTE"
    assert r["inclinacao"] > 0
    assert r["projecoes"][0]["valor"] >= 40
    assert len(r["projecoes"]) == 2


def test_tendencia_decrescente():
    r = forecast.forecast_series([100, 80, 60, 40])
    assert r["tendencia"] == "DECRESCENTE"
    assert r["inclinacao"] < 0


def test_projecao_nunca_negativa():
    r = forecast.forecast_series([30, 20, 10], horizonte=5)
    for p in r["projecoes"]:
        assert p["valor"] >= 0.0
        assert p["intervalo"][0] >= 0.0


def test_serie_estavel():
    r = forecast.forecast_series([50, 50, 50, 50])
    assert r["tendencia"] == "ESTAVEL"
    assert r["inclinacao"] == 0.0
