"""Testes do núcleo puro do Settlement Optimizer (services/settlement_optimizer/optimize.py)."""
import pytest

from services.settlement_optimizer import optimize as opt


def test_zopa_existe_com_custos():
    # p=0.5, V=100k → EV_autor=50k-8k=42k; EV_reu=50k+12k=62k → ZOPA [42k,62k]
    r = opt.optimize_settlement(100000, prob_favorable=0.5, custo_autor=8000, custo_reu=12000)
    assert r["tem_zopa"] is True
    assert r["faixa_acordo"][0] == pytest.approx(42000, abs=1)
    assert r["faixa_acordo"][1] == pytest.approx(62000, abs=1)
    assert r["recomendacao"] == "ACORDAR"


def test_blend_prob_media_modelo_e_jurimetria():
    r = opt.optimize_settlement(100000, prob_favorable=0.8, pct_provimento=0.4)
    assert r["prob_procedencia"] == pytest.approx(0.6, abs=1e-4)


def test_sem_custos_zopa_degenera_para_ponto():
    # p=0.5, sem custos → EV_autor==EV_reu==50k → ZOPA degenerada mas válida
    r = opt.optimize_settlement(100000, prob_favorable=0.5)
    assert r["tem_zopa"] is True
    assert r["acordo_sugerido"] == pytest.approx(50000, abs=1)


def test_teto_limitado_pelo_valor_causa():
    r = opt.optimize_settlement(100000, prob_favorable=1.0, custo_reu=50000)
    # EV_reu = 100k+50k=150k, mas teto é limitado ao valor da causa
    assert r["faixa_acordo"][1] <= 100000


def test_valor_negativo_levanta():
    with pytest.raises(ValueError):
        opt.optimize_settlement(-1)


def test_sem_sinais_prob_indiferente():
    r = opt.optimize_settlement(100000)
    assert r["prob_procedencia"] == 0.5
