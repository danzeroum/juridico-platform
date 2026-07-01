"""Testes do ncm_matcher: lookup exato + fuzzy + limiar de conflito."""
from __future__ import annotations

from services.fiscal.triage.ncm_matcher import (
    match_exact,
    match_fuzzy,
)
from services.shared.contracts.fiscal import FonteRegra

CATALOGO = [
    ("84713012", "Máquinas automáticas para processamento de dados, portáteis, peso até 10 kg"),
    ("22021000", "Águas, incluídas as águas minerais e gaseificadas, com adição de açúcar"),
    ("94036000", "Móveis de madeira para outros usos"),
]


class TestMatchExact:
    def test_lookup_exato_confidence_1(self):
        row = {"ncm_codigo": "84713012", "descricao": "Notebook oficial"}
        cand = match_exact("84713012", row)
        assert cand is not None
        assert cand.ncm_codigo == "84713012"
        assert cand.confidence == 1.0
        assert cand.fonte_regra == FonteRegra.TIPI

    def test_sem_hint_retorna_none(self):
        assert match_exact(None, {"ncm_codigo": "x", "descricao": "y"}) is None

    def test_codigo_inexistente_retorna_none(self):
        assert match_exact("84713012", None) is None


class TestMatchFuzzy:
    def test_descricao_similar_encontra_candidato(self):
        cand, conflito = match_fuzzy(
            "maquinas automaticas processamento de dados portateis", CATALOGO, threshold=0.5
        )
        assert cand is not None
        assert cand.ncm_codigo == "84713012"
        assert cand.fonte_regra == FonteRegra.FUZZY
        assert not conflito

    def test_baixa_similaridade_marca_conflito(self):
        cand, conflito = match_fuzzy("parafuso sextavado inox", CATALOGO, threshold=0.95)
        # Encontra o melhor candidato, mas sinaliza conflito por baixa confiança.
        assert conflito is True

    def test_catalogo_vazio_retorna_conflito(self):
        cand, conflito = match_fuzzy("qualquer coisa", [])
        assert cand is None
        assert conflito is True

    def test_descricao_vazia_retorna_conflito(self):
        cand, conflito = match_fuzzy("", CATALOGO)
        assert cand is None
        assert conflito is True
