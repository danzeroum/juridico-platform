"""
Suite de contrato do ScoreEngine.

Esta e a peca que torna a troca Python -> Rust SEGURA. Toda propriedade aqui
roda contra CADA implementacao disponivel. Quando o crate Rust existir, ele
participa automaticamente — e o teste de equivalencia cruzada exige que Python
e Rust produzam o MESMO score para os mesmos inputs. Se divergirem, o CI quebra
antes de chegar a producao.

Rode com: pytest services/scoring/tests/contract/test_score_engine_contract.py
"""
from __future__ import annotations

import pytest

from services.scoring.engine.engines import PythonScoreEngine, RustScoreEngine
from services.shared.contracts.scoring import (
    CONTRACT_VERSION,
    ScoreEngine,
    ScoreRequest,
)


def available_engines() -> list[ScoreEngine]:
    engines: list[ScoreEngine] = [PythonScoreEngine()]
    rust = RustScoreEngine()
    if rust.healthy():
        engines.append(rust)
    return engines


SAMPLE_REQUESTS = [
    ScoreRequest(cnpj="12345678000195", cnae_2dig="62", features={
        "processos_ativos": 3, "processos_trabalhistas": 1,
        "divida_ativa_valor_log": 4.2, "divida_ativa_crescimento": 0.1,
        "saldo_emprego_12m": 12, "capital_social_log": 6.0,
        "processos_repetitivos": 0,
    }),
    ScoreRequest(cnpj="11222333000181", cnae_2dig="41", features={}),
    ScoreRequest(cnpj="99888777000166", cnae_2dig="86", features={
        "processos_ativos": 80, "divida_ativa_valor_log": 9.9,
    }),
]


@pytest.fixture(params=available_engines(), ids=lambda e: e.name)
def engine(request) -> ScoreEngine:
    return request.param


@pytest.mark.parametrize("req", SAMPLE_REQUESTS, ids=lambda r: r.cnpj)
def test_score_dentro_do_intervalo(engine: ScoreEngine, req: ScoreRequest):
    result = engine.score(req)
    assert 0 <= result.score <= 1000


@pytest.mark.parametrize("req", SAMPLE_REQUESTS, ids=lambda r: r.cnpj)
def test_deterministico(engine: ScoreEngine, req: ScoreRequest):
    a = engine.score(req)
    b = engine.score(req)
    assert a.score == b.score
    assert a.confidence_interval == b.confidence_interval


@pytest.mark.parametrize("req", SAMPLE_REQUESTS, ids=lambda r: r.cnpj)
def test_intervalo_de_confianca_coerente(engine: ScoreEngine, req: ScoreRequest):
    result = engine.score(req)
    lo, hi = result.confidence_interval
    assert 0 <= lo <= hi <= 1000


@pytest.mark.parametrize("req", SAMPLE_REQUESTS, ids=lambda r: r.cnpj)
def test_breakdown_apenas_de_features_conhecidas(engine: ScoreEngine, req: ScoreRequest):
    result = engine.score(req)
    assert set(result.breakdown).issubset(set(req.features) | {
        "processos_ativos", "processos_trabalhistas", "divida_ativa_valor_log",
        "divida_ativa_crescimento", "saldo_emprego_12m", "capital_social_log",
        "processos_repetitivos",
    })


@pytest.mark.parametrize("req", SAMPLE_REQUESTS, ids=lambda r: r.cnpj)
def test_versao_do_contrato(engine: ScoreEngine, req: ScoreRequest):
    assert engine.score(req).contract_version == CONTRACT_VERSION


@pytest.mark.parametrize("req", SAMPLE_REQUESTS, ids=lambda r: r.cnpj)
def test_equivalencia_python_vs_rust(req: ScoreRequest):
    """O teste que protege a migracao: as duas implementacoes tem de concordar."""
    rust = RustScoreEngine()
    if not rust.healthy():
        pytest.skip("crate Rust nao compilado; nada a comparar")
    py_result = PythonScoreEngine().score(req)
    rust_result = rust.score(req)
    assert py_result.score == rust_result.score, (
        f"divergencia Python({py_result.score}) vs Rust({rust_result.score})"
    )
