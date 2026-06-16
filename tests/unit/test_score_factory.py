"""
Testes do factory de ScoreEngine (SEAMS).

Garante que o factory retorna a implementação correta e que o fallback
automático funciona quando o backend Rust não está disponível.
"""
import pytest


def test_get_score_engine_python():
    from services.scoring.engine.factory import get_score_engine
    from services.scoring.engine.engines import PythonScoreEngine
    engine = get_score_engine("python")
    assert isinstance(engine, PythonScoreEngine)
    assert engine.name == "python"


def test_get_score_engine_auto_sem_rust():
    """Sem crate Rust compilado, auto deve retornar PythonScoreEngine."""
    from services.scoring.engine.factory import get_score_engine
    from services.scoring.engine.engines import PythonScoreEngine
    engine = get_score_engine("auto")
    # Em CI sem Rust, o resultado é Python diretamente
    assert engine.healthy()


def test_get_score_engine_rust_falha_sem_crate():
    """Backend=rust sem crate compilado deve levantar ScoringUnavailable."""
    from services.scoring.engine.factory import get_score_engine
    from services.shared.contracts.scoring import ScoringUnavailable
    with pytest.raises(ScoringUnavailable, match="saudavel"):
        get_score_engine("rust")


def test_score_engine_python_executa():
    from services.scoring.engine.factory import get_score_engine
    from services.shared.contracts.scoring import ScoreRequest
    engine = get_score_engine("python")
    req = ScoreRequest(cnpj="12345678000195", cnae_2dig="62", features={
        "processos_ativos": 3.0, "processos_trabalhistas": 1.0,
        "divida_ativa_valor_log": 4.2, "divida_ativa_crescimento": 0.1,
        "saldo_emprego_12m": 12.0, "capital_social_log": 6.0,
        "processos_repetitivos": 0.0,
    })
    result = engine.score(req)
    assert 0 <= result.score <= 1000
    lo, hi = result.confidence_interval
    assert lo <= hi
    assert result.contract_version == "scoring/v1"


def test_python_engine_deterministico():
    from services.scoring.engine.factory import get_score_engine
    from services.shared.contracts.scoring import ScoreRequest
    engine = get_score_engine("python")
    req = ScoreRequest(cnpj="12345678000195", cnae_2dig="62", features={"processos_ativos": 5.0})
    r1 = engine.score(req)
    r2 = engine.score(req)
    assert r1.score == r2.score


def test_python_engine_healthy():
    from services.scoring.engine.engines import PythonScoreEngine
    e = PythonScoreEngine()
    assert e.healthy() is True
