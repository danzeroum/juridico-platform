"""Testes dos contratos e utilitários TaxPredict."""
from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from services.shared.contracts.taxpredict import (
    PRIOR_CI_LOWER,
    PRIOR_CI_UPPER,
    PRIOR_NACIONAL,
    TAXPREDICT_CONTRACT_VERSION,
    Decisao,
    JurisprudenciaHit,
    Materia,
    TaxPredictRequest,
    TaxPredictResponse,
    extract_features,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def req_valido():
    return {
        "descricao": "Auto de infração por suposta omissão de receitas de PIS/COFINS",
        "materia": "PIS_COFINS",
        "valor": 150_000.0,
        "orgao_autuante": "RFB",
        "ano_autuacao": 2022,
    }


# ---------------------------------------------------------------------------
# TaxPredictRequest — validação
# ---------------------------------------------------------------------------

class TestTaxPredictRequest:
    def test_valido(self, req_valido):
        r = TaxPredictRequest(**req_valido)
        assert r.materia == Materia.PIS_COFINS
        assert r.valor == 150_000.0
        assert r.orgao_autuante == "RFB"

    def test_descricao_muito_curta(self, req_valido):
        req_valido["descricao"] = "Curta demais"
        with pytest.raises(ValidationError):
            TaxPredictRequest(**req_valido)

    def test_descricao_muito_longa(self, req_valido):
        req_valido["descricao"] = "A" * 2001
        with pytest.raises(ValidationError):
            TaxPredictRequest(**req_valido)

    def test_materia_invalida(self, req_valido):
        req_valido["materia"] = "CONTRIBUICAO_INVALIDA"
        with pytest.raises(ValidationError):
            TaxPredictRequest(**req_valido)

    def test_valor_negativo(self, req_valido):
        req_valido["valor"] = -1.0
        with pytest.raises(ValidationError):
            TaxPredictRequest(**req_valido)

    def test_valor_zero_valido(self, req_valido):
        req_valido["valor"] = 0.0
        r = TaxPredictRequest(**req_valido)
        assert r.valor == 0.0

    def test_ano_autuacao_fora_do_range_inferior(self, req_valido):
        req_valido["ano_autuacao"] = 1999
        with pytest.raises(ValidationError):
            TaxPredictRequest(**req_valido)

    def test_ano_autuacao_fora_do_range_superior(self, req_valido):
        req_valido["ano_autuacao"] = 2101
        with pytest.raises(ValidationError):
            TaxPredictRequest(**req_valido)

    def test_campos_opcionais_none(self, req_valido):
        req_valido.pop("valor")
        req_valido.pop("orgao_autuante")
        req_valido.pop("ano_autuacao")
        r = TaxPredictRequest(**req_valido)
        assert r.valor is None
        assert r.orgao_autuante is None
        assert r.ano_autuacao is None

    def test_frozen_nao_permite_mutacao(self, req_valido):
        r = TaxPredictRequest(**req_valido)
        with pytest.raises(ValidationError):
            r.materia = Materia.IRPJ  # type: ignore[misc]

    def test_extra_field_proibido(self, req_valido):
        req_valido["campo_extra"] = "invalido"
        with pytest.raises(ValidationError):
            TaxPredictRequest(**req_valido)

    def test_todas_as_materias(self):
        base = "Descrição de auto de infração com detalhamento suficiente para teste"
        for m in Materia:
            r = TaxPredictRequest(descricao=base, materia=m)
            assert r.materia == m


# ---------------------------------------------------------------------------
# JurisprudenciaHit
# ---------------------------------------------------------------------------

class TestJurisprudenciaHit:
    def test_defaults(self):
        h = JurisprudenciaHit(doc_id="AC-2021-123", similarity=0.87, ementa="Ementa teste")
        assert h.decisao == Decisao.DESCONHECIDO
        assert h.tribunal is None
        assert h.ano is None

    def test_similarity_acima_de_1_invalido(self):
        with pytest.raises(ValidationError):
            JurisprudenciaHit(doc_id="x", similarity=1.5, ementa="e")

    def test_similarity_negativa_invalida(self):
        with pytest.raises(ValidationError):
            JurisprudenciaHit(doc_id="x", similarity=-0.1, ementa="e")

    def test_todos_os_campos(self):
        h = JurisprudenciaHit(
            doc_id="RESP-2022-456",
            similarity=0.92,
            ementa="Tributação de PIS/COFINS sobre receitas financeiras",
            decisao=Decisao.FAVORAVEL,
            tribunal="STJ",
            ano=2022,
        )
        assert h.decisao == Decisao.FAVORAVEL
        assert h.tribunal == "STJ"
        assert h.ano == 2022


# ---------------------------------------------------------------------------
# TaxPredictResponse
# ---------------------------------------------------------------------------

class TestTaxPredictResponse:
    def test_fallback_prior(self):
        r = TaxPredictResponse(
            materia="PIS_COFINS",
            probability=PRIOR_NACIONAL,
            ci_lower=PRIOR_CI_LOWER,
            ci_upper=PRIOR_CI_UPPER,
            rag_hits=0,
            computed_at="2026-06-16T00:00:00+00:00",
            model_version="prior_nacional_v1",
            is_fallback=True,
        )
        assert r.is_fallback is True
        assert r.contract_version == TAXPREDICT_CONTRACT_VERSION
        assert r.probability == PRIOR_NACIONAL
        assert r.jurisprudencias == []

    def test_probability_acima_de_1_invalida(self):
        with pytest.raises(ValidationError):
            TaxPredictResponse(
                materia="IRPJ",
                probability=1.5,
                ci_lower=0.1,
                ci_upper=0.9,
                rag_hits=0,
                computed_at="2026-06-16T00:00:00+00:00",
                model_version="v1",
            )

    def test_rag_hits_negativo_invalido(self):
        with pytest.raises(ValidationError):
            TaxPredictResponse(
                materia="ICMS",
                probability=0.5,
                ci_lower=0.3,
                ci_upper=0.7,
                rag_hits=-1,
                computed_at="2026-06-16T00:00:00+00:00",
                model_version="v1",
            )


# ---------------------------------------------------------------------------
# extract_features
# ---------------------------------------------------------------------------

class TestExtractFeatures:
    def test_valor_log_escala(self, req_valido):
        r = TaxPredictRequest(**req_valido)
        feats = extract_features(r)
        expected = math.log10(150_000.0 + 1) / 10.0
        assert feats["valor_log"] == pytest.approx(expected, abs=1e-4)

    def test_valor_none_retorna_zero(self, req_valido):
        req_valido["valor"] = None
        r = TaxPredictRequest(**req_valido)
        feats = extract_features(r)
        assert feats["valor_log"] == 0.0

    def test_recencia_ano_ref(self, req_valido):
        req_valido["ano_autuacao"] = 2024  # _ANO_REF → recencia = 1.0
        r = TaxPredictRequest(**req_valido)
        feats = extract_features(r)
        assert feats["recencia"] == pytest.approx(1.0, abs=1e-4)

    def test_recencia_10_anos_atras(self, req_valido):
        req_valido["ano_autuacao"] = 2014  # 10 anos → 1.0 - 10*0.1 = 0.0
        r = TaxPredictRequest(**req_valido)
        feats = extract_features(r)
        assert feats["recencia"] == pytest.approx(0.0, abs=1e-4)

    def test_recencia_nao_negativa(self, req_valido):
        req_valido["ano_autuacao"] = 2000  # muito antigo → piso 0.0
        r = TaxPredictRequest(**req_valido)
        feats = extract_features(r)
        assert feats["recencia"] >= 0.0

    def test_recencia_sem_ano_retorna_1(self, req_valido):
        req_valido.pop("ano_autuacao")
        r = TaxPredictRequest(**req_valido)
        feats = extract_features(r)
        assert feats["recencia"] == pytest.approx(1.0, abs=1e-4)

    def test_indicador_pis_cofins(self, req_valido):
        r = TaxPredictRequest(**req_valido)
        feats = extract_features(r)
        assert feats["indicador_economico"] == 0.80

    def test_indicador_simples(self, req_valido):
        req_valido["materia"] = "SIMPLES"
        r = TaxPredictRequest(**req_valido)
        feats = extract_features(r)
        assert feats["indicador_economico"] == 0.20

    def test_indicador_irpj(self, req_valido):
        req_valido["materia"] = "IRPJ"
        r = TaxPredictRequest(**req_valido)
        feats = extract_features(r)
        assert feats["indicador_economico"] == 0.70

    def test_features_tem_tres_chaves(self, req_valido):
        r = TaxPredictRequest(**req_valido)
        feats = extract_features(r)
        assert set(feats.keys()) == {"valor_log", "recencia", "indicador_economico"}

    def test_features_sao_float(self, req_valido):
        r = TaxPredictRequest(**req_valido)
        feats = extract_features(r)
        for v in feats.values():
            assert isinstance(v, float)
