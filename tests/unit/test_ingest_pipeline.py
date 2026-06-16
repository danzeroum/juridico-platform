"""
Testes do pipeline de ingestão: linage, circuit breaker, transforms de qualidade.

Não requerem serviços externos.
"""

import time

import pytest

# ── Linage ────────────────────────────────────────────────────────────────────

class TestAddLinage:
    def _fn(self):
        from services.ingest.pipeline.base import add_linage
        return add_linage

    def test_adds_required_fields(self):
        add_linage = self._fn()
        result = add_linage({"key": "val"}, source="DATAJUD")
        assert result["source"] == "DATAJUD"
        assert "ingested_at" in result
        assert result["transform_version"] == "1.0.0"

    def test_custom_transform_version(self):
        add_linage = self._fn()
        result = add_linage({}, source="PGFN", transform_version="2.0.0")
        assert result["transform_version"] == "2.0.0"

    def test_does_not_mutate_original(self):
        add_linage = self._fn()
        original = {"a": 1}
        result = add_linage(original, source="RECEITA")
        assert "source" not in original
        assert result["source"] == "RECEITA"

    def test_ingested_at_is_iso_format(self):
        add_linage = self._fn()
        result = add_linage({}, source="DATAJUD")
        # ISO 8601 format check
        from datetime import datetime
        dt = datetime.fromisoformat(result["ingested_at"].replace("Z", "+00:00"))
        assert dt is not None


class TestComputeLagDays:
    def _fn(self):
        from services.ingest.pipeline.base import compute_lag_days
        return compute_lag_days

    def test_today_is_zero(self):
        from datetime import date
        compute_lag_days = self._fn()
        today = date.today().isoformat()
        assert compute_lag_days(today) == 0

    def test_yesterday_is_one(self):
        from datetime import date, timedelta
        compute_lag_days = self._fn()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        assert compute_lag_days(yesterday) == 1

    def test_invalid_date_returns_minus_one(self):
        compute_lag_days = self._fn()
        assert compute_lag_days("not-a-date") == -1

    def test_none_returns_minus_one(self):
        compute_lag_days = self._fn()
        assert compute_lag_days(None) == -1


class TestReconcile:
    def _fn(self):
        from services.ingest.pipeline.base import reconcile
        return reconcile

    def test_zero_loss(self):
        reconcile = self._fn()
        rec = reconcile("DATAJUD", 100, 100, "2024-01-01")
        assert rec["loss_pct"] == 0.0
        assert rec["records_in"] == 100
        assert rec["records_out"] == 100

    def test_partial_loss(self):
        reconcile = self._fn()
        rec = reconcile("DATAJUD", 100, 90, "2024-01-01")
        assert rec["loss_pct"] == 10.0

    def test_zero_records_in(self):
        reconcile = self._fn()
        rec = reconcile("DATAJUD", 0, 0, "2024-01-01")
        assert rec["loss_pct"] == 0.0


# ── CircuitBreaker ─────────────────────────────────────────────────────────────

class TestCircuitBreaker:
    def _cls(self):
        from services.ingest.pipeline.base import CircuitBreaker, CircuitState
        return CircuitBreaker, CircuitState

    def test_starts_closed(self):
        CircuitBreaker, CircuitState = self._cls()
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED
        assert not cb.is_open()

    def test_opens_after_threshold(self):
        CircuitBreaker, CircuitState = self._cls()
        cb = CircuitBreaker("test", failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_open()

    def test_success_resets_to_closed(self):
        CircuitBreaker, CircuitState = self._cls()
        cb = CircuitBreaker("test", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert not cb.is_open()

    def test_half_open_after_recovery_timeout(self):
        CircuitBreaker, CircuitState = self._cls()
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        assert cb.is_open()
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes(self):
        CircuitBreaker, CircuitState = self._cls()
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED


# ── Quality Transforms ─────────────────────────────────────────────────────────

class TestSafeLog1p:
    def _fn(self):
        from services.ingest.pipeline.base import safe_log1p
        return safe_log1p

    def test_positive_value(self):
        import math
        safe_log1p = self._fn()
        assert safe_log1p(100.0) == pytest.approx(math.log1p(100.0))

    def test_zero(self):
        safe_log1p = self._fn()
        assert safe_log1p(0.0) == 0.0

    def test_none_returns_zero(self):
        safe_log1p = self._fn()
        assert safe_log1p(None) == 0.0

    def test_negative_returns_zero(self):
        safe_log1p = self._fn()
        assert safe_log1p(-10.0) == 0.0


class TestQualityTransforms:
    def test_treat_missing_valor_causa_none(self):
        from services.ingest.pipeline.quality import treat_missing_valor_causa
        rec = treat_missing_valor_causa({"foo": "bar"})
        assert rec["valor_causa"] == 0.0
        assert rec["valor_causa_imputado"] is True

    def test_treat_missing_valor_causa_present(self):
        from services.ingest.pipeline.quality import treat_missing_valor_causa
        rec = treat_missing_valor_causa({"valor_causa": 500.0})
        assert rec["valor_causa"] == 500.0
        assert rec["valor_causa_imputado"] is False

    def test_remove_outliers_over_limit(self):
        from services.ingest.pipeline.quality import remove_outliers_valor
        rec = remove_outliers_valor({"valor_causa": 2e12})
        assert rec["valor_causa"] is None
        assert rec["valor_causa_outlier"] is True

    def test_remove_outliers_under_limit(self):
        from services.ingest.pipeline.quality import remove_outliers_valor
        rec = remove_outliers_valor({"valor_causa": 50000.0})
        assert rec["valor_causa"] == 50000.0
        assert rec["valor_causa_outlier"] is False

    def test_add_valor_log(self):
        import math

        from services.ingest.pipeline.quality import add_valor_log
        rec = add_valor_log({"valor_causa": 100.0})
        assert rec["valor_log"] == pytest.approx(math.log1p(100.0))

    def test_add_recencia_valid_date(self):
        from datetime import date

        from services.ingest.pipeline.quality import add_recencia
        today = date.today().isoformat()
        rec = add_recencia({"data_julgamento": today})
        assert rec["recencia_dias"] == 0
        assert rec["recencia"] == 0.0

    def test_pgfn_bronze_to_silver_sem_divida(self):
        from services.ingest.pipeline.quality import pgfn_bronze_to_silver
        silver = pgfn_bronze_to_silver({
            "cnpj": "11222333000181",
            "situacao": "REGULAR",
            "valor_total_divida": None,
        })
        assert silver["valor_total_divida"] == 0.0
        assert silver["valor_divida_log"] == 0.0
        assert silver["tem_divida_ativa"] is False

    def test_pgfn_bronze_to_silver_com_divida(self):
        import math

        from services.ingest.pipeline.quality import pgfn_bronze_to_silver
        silver = pgfn_bronze_to_silver({
            "cnpj": "11222333000181",
            "situacao": "IRREGULAR",
            "valor_total_divida": 50000.0,
        })
        assert silver["tem_divida_ativa"] is True
        assert silver["valor_divida_log"] == pytest.approx(math.log1p(50000.0))

    def test_receita_bronze_to_silver_ativa(self):
        from services.ingest.pipeline.quality import receita_bronze_to_silver
        silver = receita_bronze_to_silver({
            "cnpj": "11222333000181",
            "situacao_cadastral": "ATIVA",
            "capital_social": 1000.0,
            "data_abertura": "2010-06-15",
        })
        assert silver["esta_ativa"] is True
        assert silver["capital_social_log"] > 0
        assert silver["idade_empresa_anos"] is not None
        assert silver["idade_empresa_anos"] > 0

    def test_receita_bronze_to_silver_baixada(self):
        from services.ingest.pipeline.quality import receita_bronze_to_silver
        silver = receita_bronze_to_silver({
            "cnpj": "11222333000181",
            "situacao_cadastral": "BAIXADA",
            "capital_social": None,
        })
        assert silver["esta_ativa"] is False
        assert silver["capital_social"] == 0.0


def test_get_circuit_breaker_cria_e_reutiliza():
    """get_circuit_breaker deve criar na primeira chamada e reutilizar na segunda."""
    from services.ingest.pipeline.base import _breakers, get_circuit_breaker
    _breakers.clear()
    cb1 = get_circuit_breaker("test-source-xyz")
    cb2 = get_circuit_breaker("test-source-xyz")
    assert cb1 is cb2
    assert cb1.name == "test-source-xyz"
    _breakers.clear()
