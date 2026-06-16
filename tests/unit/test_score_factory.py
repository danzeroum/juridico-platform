"""
Testes do factory de ScoreEngine (SEAMS).

Garante que o factory retorna a implementação correta e que o fallback
automático funciona quando o backend Rust não está disponível.
"""
import pytest


def test_get_score_engine_python():
    from services.scoring.engine.engines import PythonScoreEngine
    from services.scoring.engine.factory import get_score_engine
    engine = get_score_engine("python")
    assert isinstance(engine, PythonScoreEngine)
    assert engine.name == "python"


def test_get_score_engine_auto_sem_rust():
    """Sem crate Rust compilado, auto deve retornar PythonScoreEngine."""
    from services.scoring.engine.factory import get_score_engine
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


# ---------------------------------------------------------------------------
# _classify() — cobre BAIXO / MODERADO / ALTO / CRITICO via coeficiente forçado
# ---------------------------------------------------------------------------

def _engine_with_intercept(intercept: float):
    from services.scoring.engine.engines import PythonScoreEngine
    def loader(cnae):
        return {"intercept": intercept, "sigma": 0.0}
    return PythonScoreEngine(coefficient_loader=loader)


def test_classify_baixo():
    from services.shared.contracts.scoring import ScoreRequest
    engine = _engine_with_intercept(850.0)
    r = engine.score(ScoreRequest(cnpj="12345678000195", cnae_2dig="62", features={}))
    assert r.risk_level == "BAIXO"
    assert r.score == 850


def test_classify_moderado():
    from services.shared.contracts.scoring import ScoreRequest
    engine = _engine_with_intercept(650.0)
    r = engine.score(ScoreRequest(cnpj="12345678000195", cnae_2dig="62", features={}))
    assert r.risk_level == "MODERADO"
    assert r.score == 650


def test_classify_alto():
    from services.shared.contracts.scoring import ScoreRequest
    engine = _engine_with_intercept(500.0)
    r = engine.score(ScoreRequest(cnpj="12345678000195", cnae_2dig="62", features={}))
    assert r.risk_level == "ALTO"
    assert r.score == 500


def test_classify_critico():
    from services.shared.contracts.scoring import ScoreRequest
    engine = _engine_with_intercept(200.0)
    r = engine.score(ScoreRequest(cnpj="12345678000195", cnae_2dig="62", features={}))
    assert r.risk_level == "CRITICO"
    assert r.score == 200


# ---------------------------------------------------------------------------
# _FallbackEngine — testado diretamente com mocks
# ---------------------------------------------------------------------------

class _StubEngine:
    def __init__(self, name: str, healthy: bool = True, raise_on_score=None):
        self.name = name
        self._healthy = healthy
        self._raise = raise_on_score

    def healthy(self) -> bool:
        return self._healthy

    def score(self, request):
        if self._raise:
            raise self._raise
        from services.shared.contracts.scoring import ScoreResult
        return ScoreResult(
            score=777,
            confidence_interval=(700, 800),
            risk_level="BAIXO",
            engine=self.name,
            breakdown={},
            contract_version="scoring/v1",
        )


def test_fallback_engine_healthy_when_primary_ok():
    from services.scoring.engine.factory import _FallbackEngine
    fb = _FallbackEngine(_StubEngine("p", healthy=True), _StubEngine("s", healthy=False))
    assert fb.healthy() is True
    assert fb.name == "p->s"


def test_fallback_engine_healthy_when_secondary_ok():
    from services.scoring.engine.factory import _FallbackEngine
    fb = _FallbackEngine(_StubEngine("p", healthy=False), _StubEngine("s", healthy=True))
    assert fb.healthy() is True


def test_fallback_engine_healthy_false_when_both_down():
    from services.scoring.engine.factory import _FallbackEngine
    fb = _FallbackEngine(_StubEngine("p", healthy=False), _StubEngine("s", healthy=False))
    assert fb.healthy() is False


def test_fallback_engine_score_uses_primary():
    from services.scoring.engine.factory import _FallbackEngine
    from services.shared.contracts.scoring import ScoreRequest
    fb = _FallbackEngine(_StubEngine("p"), _StubEngine("s"))
    req = ScoreRequest(cnpj="12345678000195", cnae_2dig="62", features={})
    result = fb.score(req)
    assert result.score == 777


def test_fallback_engine_score_falls_back_on_unavailable():
    from services.scoring.engine.factory import _FallbackEngine
    from services.shared.contracts.scoring import ScoreRequest, ScoringUnavailable
    primary = _StubEngine("p", raise_on_score=ScoringUnavailable("boom"))
    secondary = _StubEngine("s")
    fb = _FallbackEngine(primary, secondary)
    req = ScoreRequest(cnpj="12345678000195", cnae_2dig="62", features={})
    result = fb.score(req)
    assert result.score == 777


def test_score_result_confidence_interval_invalido():
    """lower > upper deve levantar ValueError."""
    from pydantic import ValidationError

    from services.shared.contracts.scoring import ScoreResult
    with pytest.raises(ValidationError, match="invalido"):
        ScoreResult(
            score=700,
            confidence_interval=(800, 700),  # lo > hi — inválido
            risk_level="BAIXO",
            engine="python",
            breakdown={},
        )
