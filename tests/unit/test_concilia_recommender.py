"""Testes do ConciliaIA recommender."""
from __future__ import annotations

import pytest

from services.concilia.recommender import _BASE_PCT, recommend_settlement
from services.shared.contracts.concilia import ConciliaRequest, ConciliaResponse, TipoAcao


def _make_req(tipo: str = "TRABALHISTA", valor: float = 100_000.0) -> ConciliaRequest:
    return ConciliaRequest(
        descricao="Reclamação trabalhista por horas extras não pagas durante o vínculo.",
        valor_causa=valor,
        tipo_acao=TipoAcao(tipo),
    )


class TestRecommendSettlement:
    def test_retorna_conciliaresponse(self):
        req = _make_req()
        resp = recommend_settlement(req)
        assert isinstance(resp, ConciliaResponse)

    def test_prior_historico_trabalhista(self):
        req = _make_req("TRABALHISTA", 100_000.0)
        resp = recommend_settlement(req)
        base = _BASE_PCT["TRABALHISTA"]
        assert resp.valor_sugerido == pytest.approx(100_000.0 * base, abs=0.01)

    def test_prior_historico_tributario(self):
        req = _make_req("TRIBUTARIO", 200_000.0)
        resp = recommend_settlement(req)
        base = _BASE_PCT["TRIBUTARIO"]
        assert resp.valor_sugerido == pytest.approx(200_000.0 * base, abs=0.01)

    def test_valor_minimo_menor_que_sugerido(self):
        resp = recommend_settlement(_make_req())
        assert resp.valor_minimo < resp.valor_sugerido

    def test_valor_maximo_maior_que_sugerido(self):
        resp = recommend_settlement(_make_req())
        assert resp.valor_maximo >= resp.valor_sugerido

    def test_valor_maximo_nao_excede_causa(self):
        req = _make_req(valor=100_000.0)
        resp = recommend_settlement(req)
        assert resp.valor_maximo <= 100_000.0

    def test_percentual_causa_consistente(self):
        req = _make_req(valor=100_000.0)
        resp = recommend_settlement(req)
        assert resp.percentual_causa == pytest.approx(resp.valor_sugerido / 100_000.0, abs=1e-4)

    def test_ajuste_probability_favoravel_alta(self):
        req = _make_req("TRABALHISTA", 100_000.0)
        resp_sem = recommend_settlement(req)
        resp_com = recommend_settlement(req, probability_favorable=0.90)
        assert resp_com.valor_sugerido > resp_sem.valor_sugerido

    def test_ajuste_probability_favoravel_baixa(self):
        req = _make_req("TRABALHISTA", 100_000.0)
        resp_sem = recommend_settlement(req)
        resp_com = recommend_settlement(req, probability_favorable=0.05)
        assert resp_com.valor_sugerido < resp_sem.valor_sugerido

    def test_ajuste_risco_reu_alto(self):
        req = _make_req(valor=100_000.0)
        resp_sem = recommend_settlement(req)
        resp_com = recommend_settlement(req, risk_score_reu=900)
        assert resp_com.valor_sugerido > resp_sem.valor_sugerido

    def test_ajuste_risco_reu_baixo(self):
        req = _make_req(valor=100_000.0)
        resp_sem = recommend_settlement(req)
        resp_com = recommend_settlement(req, risk_score_reu=100)
        assert resp_com.valor_sugerido < resp_sem.valor_sugerido

    def test_fatores_incluem_prior(self):
        resp = recommend_settlement(_make_req())
        nomes = [f.nome for f in resp.fatores]
        assert "Prior histórico" in nomes

    def test_fatores_incluem_probability_se_fornecida(self):
        resp = recommend_settlement(_make_req(), probability_favorable=0.7)
        nomes = [f.nome for f in resp.fatores]
        assert "Probabilidade de procedência" in nomes

    def test_fatores_incluem_risco_se_fornecido(self):
        resp = recommend_settlement(_make_req(), risk_score_reu=500)
        nomes = [f.nome for f in resp.fatores]
        assert "Risco do réu (LegalScore)" in nomes

    def test_percentual_causa_dentro_limites(self):
        for tipo in ("TRABALHISTA", "TRIBUTARIO", "CIVEL", "CONSUMERISTA"):
            resp = recommend_settlement(_make_req(tipo))
            assert 0.0 <= resp.percentual_causa <= 1.0

    def test_risco_reu_preservado_na_resposta(self):
        resp = recommend_settlement(_make_req(), risk_score_reu=700)
        assert resp.risco_reu == 700

    def test_probability_preservada_na_resposta(self):
        resp = recommend_settlement(_make_req(), probability_favorable=0.65)
        assert resp.probabilidade_procedencia == pytest.approx(0.65, abs=1e-6)


class TestConciliaContracts:
    def test_request_valido(self):
        r = ConciliaRequest(
            descricao="Ação trabalhista por rescisão indireta motivada por não pagamento.",
            valor_causa=80_000.0,
            tipo_acao="CIVEL",
        )
        assert r.valor_causa == 80_000.0

    def test_valor_causa_zero_invalido(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ConciliaRequest(
                descricao="Descrição suficientemente longa para validação.",
                valor_causa=0.0,
                tipo_acao="CIVEL",
            )

    def test_cnpj_invalido(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ConciliaRequest(
                descricao="Descrição suficientemente longa para validação.",
                valor_causa=50_000.0,
                tipo_acao="CIVEL",
                cnpj_reu="123",
            )
