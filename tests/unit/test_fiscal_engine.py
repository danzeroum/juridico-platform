"""Testes do engine.classify: orquestração determinística, pura (sem Ledger)."""
from __future__ import annotations

from services.fiscal.triage.engine import classify
from services.shared.contracts.fiscal import UF, NcmTriageRequest


class FakeNcmSource:
    def __init__(self, rows: dict[str, dict], catalog: list[tuple[str, str]]):
        self._rows = rows
        self._catalog = catalog

    def get_ncm(self, codigo, data):
        return self._rows.get(codigo)

    def catalog(self, data):
        return self._catalog


class FakeIcmsSource:
    def __init__(self, interna: dict | None):
        self._interna = interna

    def interna(self, uf, ncm_codigo, data):
        return self._interna


class FakeCategorySource:
    def categoria(self, ncm_codigo):
        return "maquinas" if ncm_codigo == "84713012" else None


NCM_ROWS = {"84713012": {"ncm_codigo": "84713012", "descricao": "Notebook oficial"}}
CATALOG = [("84713012", "Máquinas automáticas para processamento de dados, portáteis")]
RJ_INTERNA = {"aliquota_pct": 18.0, "fcp_pct": 2.0, "fundamento_legal": "LC-RJ 210/2023"}


def _req(**kw):
    base = dict(descricao="Notebook Dell i7", uf_origem=UF.SP, uf_destino=UF.RJ)
    base.update(kw)
    return NcmTriageRequest(**base)


class TestClassify:
    def test_hint_valido_lookup_exato(self):
        res = classify(
            _req(ncm_hint="84713012"),
            FakeNcmSource(NCM_ROWS, CATALOG),
            FakeIcmsSource(RJ_INTERNA),
            FakeCategorySource(),
        )
        assert res.suggested_ncm.ncm_codigo == "84713012"
        assert res.suggested_ncm.confidence == 1.0
        assert res.conflito_detectado is False
        assert res.categoria == "maquinas"
        assert res.icms.difal_pct == 8.0
        assert res.decision_proof is None  # preenchido só na ancoragem

    def test_hint_inexistente_marca_conflito(self):
        res = classify(
            _req(ncm_hint="99999999"),
            FakeNcmSource(NCM_ROWS, CATALOG),
            FakeIcmsSource(RJ_INTERNA),
        )
        assert res.suggested_ncm is None
        assert res.conflito_detectado is True
        assert any("não encontrado" in o for o in res.observacoes)

    def test_sem_hint_usa_fuzzy(self):
        res = classify(
            _req(descricao="maquinas automaticas processamento de dados portateis"),
            FakeNcmSource(NCM_ROWS, CATALOG),
            FakeIcmsSource(RJ_INTERNA),
            fuzzy_threshold=0.5,
        )
        assert res.suggested_ncm is not None
        assert res.suggested_ncm.ncm_codigo == "84713012"

    def test_sem_aliquota_interna_gera_observacao(self):
        res = classify(
            _req(ncm_hint="84713012"),
            FakeNcmSource(NCM_ROWS, CATALOG),
            FakeIcmsSource(None),
        )
        assert res.icms.interna_efetiva_pct is None
        assert any("Sem alíquota interna" in o for o in res.observacoes)

    def test_sem_hint_sem_candidato_gera_observacao(self):
        res = classify(
            _req(descricao="produto totalmente desconhecido"),
            FakeNcmSource(NCM_ROWS, []),  # catálogo vazio → sem candidato
            FakeIcmsSource(RJ_INTERNA),
        )
        assert res.suggested_ncm is None
        assert res.conflito_detectado is True
        assert any("Não foi possível sugerir" in o for o in res.observacoes)

    def test_sem_hint_baixa_confianca_gera_observacao(self):
        res = classify(
            _req(descricao="parafuso inox"),
            FakeNcmSource(NCM_ROWS, CATALOG),
            FakeIcmsSource(RJ_INTERNA),
            fuzzy_threshold=0.99,  # força conflito por baixa confiança
        )
        assert res.conflito_detectado is True
        assert any("baixa confiança" in o for o in res.observacoes)

    def test_determinismo(self):
        args = (
            _req(ncm_hint="84713012"),
            FakeNcmSource(NCM_ROWS, CATALOG),
            FakeIcmsSource(RJ_INTERNA),
        )
        assert classify(*args).model_dump() == classify(*args).model_dump()
