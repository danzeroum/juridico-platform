"""
Testes do feature assembler (Fase 1b).

Usa mock de Redis — não requer serviços externos.
"""

import json
import math
from unittest.mock import MagicMock

import pytest


def _make_redis(pgfn_data=None, receita_data=None):
    """Cria mock Redis que responde com os dados fornecidos."""
    mock = MagicMock()

    def get(key):
        if key.startswith("pgfn:") and pgfn_data is not None:
            return json.dumps(pgfn_data).encode()
        if key.startswith("receita:") and receita_data is not None:
            return json.dumps(receita_data).encode()
        return None

    mock.get.side_effect = get
    return mock


class TestAssembleFeatures:
    def _fn(self):
        from services.scoring.features import assemble_features
        return assemble_features

    def test_no_cache_returns_zeros(self):
        assemble_features = self._fn()
        redis = _make_redis()  # todos os gets retornam None
        fv = assemble_features("11222333000181", redis)
        assert fv.cnpj == "11222333000181"
        assert all(v == 0.0 for v in fv.features.values())
        assert fv.is_partial is True
        assert "PGFN" in fv.sources_missing
        assert "RECEITA" in fv.sources_missing
        assert "DATAJUD" in fv.sources_missing

    def test_pgfn_cache_fills_divida_feature(self):
        assemble_features = self._fn()
        pgfn = {
            "cnpj": "11222333000181",
            "situacao": "IRREGULAR",
            "valor_total_divida": 50000.0,
            "source": "PGFN",
            "ingested_at": "2024-01-01T00:00:00Z",
            "transform_version": "1.0.0",
        }
        redis = _make_redis(pgfn_data=pgfn)
        fv = assemble_features("11222333000181", redis)
        assert fv.features["divida_ativa_valor_log"] == pytest.approx(math.log1p(50000.0))
        assert "PGFN" in fv.sources_used

    def test_receita_cache_fills_capital_feature(self):
        assemble_features = self._fn()
        receita = {
            "cnpj": "11222333000181",
            "razao_social": "EMPRESA LTDA",
            "situacao_cadastral": "ATIVA",
            "capital_social": 100000.0,
            "cnae_fiscal": "6201501",
            "source": "RECEITA",
            "ingested_at": "2024-03-15T10:00:00Z",
            "transform_version": "1.0.0",
        }
        redis = _make_redis(receita_data=receita)
        fv = assemble_features("11222333000181", redis)
        assert fv.features["capital_social_log"] == pytest.approx(math.log1p(100000.0))
        assert "RECEITA" in fv.sources_used
        assert fv.cnae_2dig == "62"
        assert fv.source_date == "2024-03-15"

    def test_both_caches_fills_two_features(self):
        assemble_features = self._fn()
        pgfn = {"cnpj": "11222333000181", "situacao": "REGULAR", "valor_total_divida": 0.0,
                "source": "PGFN", "ingested_at": "2024-01-01", "transform_version": "1.0.0"}
        receita = {"cnpj": "11222333000181", "razao_social": "EMPRESA", "situacao_cadastral": "ATIVA",
                   "capital_social": 5000.0, "cnae_fiscal": "4711301",
                   "source": "RECEITA", "ingested_at": "2024-01-01T00:00:00Z", "transform_version": "1.0.0"}
        redis = _make_redis(pgfn_data=pgfn, receita_data=receita)
        fv = assemble_features("11222333000181", redis)
        assert "PGFN" in fv.sources_used
        assert "RECEITA" in fv.sources_used
        # DATAJUD ainda ausente (Fase 1c)
        assert "DATAJUD" in fv.sources_missing
        assert fv.is_partial is True  # DATAJUD ainda faltando

    def test_all_feature_names_present(self):
        from services.scoring.features import FEATURE_NAMES
        assemble_features = self._fn()
        redis = _make_redis()
        fv = assemble_features("11222333000181", redis)
        for name in FEATURE_NAMES:
            assert name in fv.features, f"Feature '{name}' ausente"

    def test_cnae_defaults_to_00_when_receita_missing(self):
        assemble_features = self._fn()
        redis = _make_redis()
        fv = assemble_features("11222333000181", redis)
        assert fv.cnae_2dig == "00"

    def test_broken_cache_returns_partial(self):
        """Dado corrompido no cache não deve causar exceção — retorna partial."""
        assemble_features = self._fn()
        mock = MagicMock()
        mock.get.return_value = b"NOT JSON AT ALL"
        fv = assemble_features("11222333000181", mock)
        assert fv.is_partial is True

    def test_cnpj_preserved(self):
        assemble_features = self._fn()
        fv = assemble_features("11222333000181", _make_redis())
        assert fv.cnpj == "11222333000181"


class TestScoringPipelineIntegration:
    """Testa a cadeia features → engine → resultado."""

    def test_engine_produces_valid_result_with_zero_features(self):
        from services.scoring.engine.factory import get_score_engine
        from services.scoring.features import FEATURE_NAMES
        from services.shared.contracts.scoring import ScoreRequest as EngineScoreRequest

        engine = get_score_engine("python")
        req = EngineScoreRequest(
            cnpj="11222333000181",
            features={name: 0.0 for name in FEATURE_NAMES},
            cnae_2dig="00",
        )
        result = engine.score(req)
        assert 0 <= result.score <= 1000
        assert result.risk_level in ("BAIXO", "MODERADO", "ALTO", "CRITICO")
        lo, hi = result.confidence_interval
        assert lo <= result.score <= hi

    def test_engine_produces_valid_result_with_real_features(self):
        import math

        from services.scoring.engine.factory import get_score_engine
        from services.shared.contracts.scoring import ScoreRequest as EngineScoreRequest

        engine = get_score_engine("python")
        req = EngineScoreRequest(
            cnpj="11222333000181",
            features={
                "processos_ativos": 5.0,
                "processos_trabalhistas": 2.0,
                "divida_ativa_valor_log": math.log1p(50000),
                "divida_ativa_crescimento": 0.1,
                "saldo_emprego_12m": -10.0,
                "capital_social_log": math.log1p(100000),
                "processos_repetitivos": 3.0,
            },
            cnae_2dig="62",
        )
        result = engine.score(req)
        assert 0 <= result.score <= 1000
        assert result.engine == "python"
        assert len(result.breakdown) == 7
