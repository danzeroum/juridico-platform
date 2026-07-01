"""
Testes reais da camada semântica: mapeamento hits→candidato (puro) e a integração
do fallback semântico no motor (com fonte semântica determinística fake).
O embedding real (RAG/Ollama) é validado em E2E — aqui testamos a lógica de decisão.
"""
from __future__ import annotations

from services.fiscal.triage.engine import classify
from services.fiscal.triage.semantic import hits_to_candidate
from services.shared.contracts.fiscal import UF, FonteRegra, NcmTriageRequest


class FakeNcmSource:
    def __init__(self, catalog):
        self._catalog = catalog

    def get_ncm(self, codigo, data):
        return None

    def catalog(self, data):
        return self._catalog


class FakeIcms:
    def interna(self, uf, ncm, data):
        return {"aliquota_pct": 18.0, "fcp_pct": None, "fundamento_legal": "x"}


class FakeSemantic:
    def __init__(self, hits):
        self._hits = hits

    def suggest(self, descricao, k=5):
        return self._hits


def _req(desc):
    return NcmTriageRequest(descricao=desc, uf_origem=UF.SP, uf_destino=UF.RJ)


class TestHitsToCandidate:
    def test_hit_forte_sem_conflito(self):
        cand, conflito = hits_to_candidate([("84713012", "Máquinas...", 0.91)])
        assert cand.ncm_codigo == "84713012"
        assert cand.fonte_regra == FonteRegra.RAG
        assert conflito is False

    def test_hit_fraco_marca_conflito(self):
        cand, conflito = hits_to_candidate([("22021000", "Águas...", 0.40)])
        assert cand is not None
        assert conflito is True

    def test_escolhe_melhor_score(self):
        cand, _ = hits_to_candidate([("11111111", "a", 0.3), ("22222222", "b", 0.85)])
        assert cand.ncm_codigo == "22222222"

    def test_vazio(self):
        assert hits_to_candidate([]) == (None, True)


class TestSemanticFallbackNoMotor:
    def test_semantico_resolve_onde_fuzzy_falha(self):
        # Catálogo vazio → fuzzy não sugere nada; semântico traz um hit forte.
        res = classify(
            _req("refrigerante lata 350ml"),
            FakeNcmSource([]),
            FakeIcms(),
            semantic_source=FakeSemantic([("22021000", "Águas gaseificadas com açúcar", 0.88)]),
        )
        assert res.suggested_ncm is not None
        assert res.suggested_ncm.ncm_codigo == "22021000"
        assert res.suggested_ncm.fonte_regra == FonteRegra.RAG
        assert res.conflito_detectado is False
        assert any("semântica" in o for o in res.observacoes)

    def test_semantico_fraco_mantem_conflito(self):
        res = classify(
            _req("produto obscuro"),
            FakeNcmSource([]),
            FakeIcms(),
            semantic_source=FakeSemantic([("94036000", "Móveis", 0.35)]),
        )
        assert res.conflito_detectado is True

    def test_fuzzy_confiante_nao_usa_semantico(self):
        # Fuzzy resolve com alta confiança → semântico não sobrescreve.
        catalogo = [("22021000", "refrigerante lata 350ml")]
        res = classify(
            _req("refrigerante lata 350ml"),
            FakeNcmSource(catalogo),
            FakeIcms(),
            semantic_source=FakeSemantic([("99999999", "errado", 0.99)]),
        )
        assert res.suggested_ncm.ncm_codigo == "22021000"
        assert res.suggested_ncm.fonte_regra == FonteRegra.FUZZY
