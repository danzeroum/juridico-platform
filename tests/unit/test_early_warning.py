"""Testes do núcleo puro do Early Warning System (services/early_warning/detect.py)."""
from services.early_warning import detect


def test_surto_de_volume_detectado():
    # série estável e um salto grande no fim
    r = detect.detect_surges([10, 11, 9, 10, 40])
    assert r["tem_alerta"] is True
    tipos = {g["tipo"] for g in r["gatilhos"]}
    assert "SURTO_VOLUME" in tipos


def test_sem_surto_em_serie_estavel():
    r = detect.detect_surges([10, 11, 9, 10, 10])
    assert r["tem_alerta"] is False


def test_pico_congestionamento():
    r = detect.detect_surges([10, 10, 10], taxa_congestionamento=0.9)
    tipos = {g["tipo"] for g in r["gatilhos"]}
    assert "PICO_CONGESTIONAMENTO" in tipos
    pico = next(g for g in r["gatilhos"] if g["tipo"] == "PICO_CONGESTIONAMENTO")
    assert pico["severidade"] == "HIGH"


def test_serie_curta_nao_avalia_volume():
    r = detect.detect_surges([10, 40])  # < 3 pontos
    tipos = {g["tipo"] for g in r["gatilhos"]}
    assert "SURTO_VOLUME" not in tipos


def test_variacao_percentual_dispara_mesmo_sem_zscore_alto():
    # crescimento gradual mas +50% no último passo
    r = detect.detect_surges([100, 100, 100, 160])
    assert r["tem_alerta"] is True
