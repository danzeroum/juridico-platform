"""
Testes do store de idempotência e rastreador de batch (Fase 1c).

Usa mock Redis — não requer serviços externos.
"""

from unittest.mock import MagicMock


def _make_redis() -> MagicMock:
    """Mock Redis com comportamento in-memory."""
    store: dict = {}
    ttls: dict = {}

    def setex(key, ttl, value):
        store[key] = value
        ttls[key] = ttl

    def get(key):
        v = store.get(key)
        return v.encode() if isinstance(v, str) else v

    def ttl(key):
        return ttls.get(key, -1)

    mock = MagicMock()
    mock.setex.side_effect = setex
    mock.get.side_effect = get
    mock.ttl.side_effect = ttl
    mock._store = store
    return mock


class TestIdempotencyStore:
    def test_get_missing_returns_none(self):
        from services.scoring.idempotency import get_idempotency_result
        redis = _make_redis()
        assert get_idempotency_result(redis, "tenant1", "key1") is None

    def test_set_then_get(self):
        from services.scoring.idempotency import get_idempotency_result, set_idempotency_result
        redis = _make_redis()
        set_idempotency_result(redis, "tenant1", "key1", {"score": 720})
        result = get_idempotency_result(redis, "tenant1", "key1")
        assert result is not None
        assert result["score"] == 720

    def test_different_tenants_isolated(self):
        from services.scoring.idempotency import get_idempotency_result, set_idempotency_result
        redis = _make_redis()
        set_idempotency_result(redis, "tenantA", "same_key", {"score": 100})
        assert get_idempotency_result(redis, "tenantB", "same_key") is None

    def test_set_uses_correct_ttl(self):
        from services.scoring.idempotency import set_idempotency_result
        redis = _make_redis()
        set_idempotency_result(redis, "t1", "k1", {"x": 1}, ttl_secs=3600)
        assert redis.ttl("idemp:t1:k1") == 3600

    def test_default_ttl_is_24h(self):
        from services.scoring.idempotency import set_idempotency_result
        redis = _make_redis()
        set_idempotency_result(redis, "t1", "k1", {"x": 1})
        assert redis.ttl("idemp:t1:k1") == 86400


class TestBatchJobTracker:
    def test_create_batch_job_returns_id(self):
        from services.scoring.idempotency import create_batch_job
        redis = _make_redis()
        job_id = create_batch_job(redis, ["11222333000181", "22333444000191"], "tenant1")
        assert job_id.startswith("batch_")

    def test_create_then_get_status(self):
        from services.scoring.idempotency import create_batch_job, get_batch_status
        redis = _make_redis()
        job_id = create_batch_job(redis, ["cnpj1", "cnpj2", "cnpj3"], "t1")
        status = get_batch_status(redis, job_id)
        assert status is not None
        assert status["status"] == "queued"
        assert status["total"] == 3
        assert status["processed"] == 0

    def test_get_missing_batch_returns_none(self):
        from services.scoring.idempotency import get_batch_status
        redis = _make_redis()
        assert get_batch_status(redis, "batch_nonexistent") is None

    def test_update_progress(self):
        from services.scoring.idempotency import (
            create_batch_job,
            get_batch_status,
            update_batch_progress,
        )
        redis = _make_redis()
        job_id = create_batch_job(redis, list(range(10)), "t1")
        update_batch_progress(redis, job_id, processed=5, results=[{"cnpj": "x"}], status="processing")
        status = get_batch_status(redis, job_id)
        assert status["processed"] == 5
        assert status["status"] == "processing"
        assert len(status["results"]) == 1

    def test_update_to_done(self):
        from services.scoring.idempotency import (
            create_batch_job,
            get_batch_status,
            update_batch_progress,
        )
        redis = _make_redis()
        job_id = create_batch_job(redis, ["cnpj1"], "t1")
        update_batch_progress(
            redis, job_id, processed=1,
            results=[{"cnpj": "cnpj1", "score": 800}],
            status="done",
            completed_at="2024-01-01T00:00:00Z",
        )
        status = get_batch_status(redis, job_id)
        assert status["status"] == "done"
        assert status["completed_at"] == "2024-01-01T00:00:00Z"
        assert status["results"][0]["score"] == 800

    def test_update_nonexistent_job_is_noop(self):
        from services.scoring.idempotency import update_batch_progress
        redis = _make_redis()
        # Não deve lançar exceção
        update_batch_progress(redis, "batch_ghost", 0, [], "done")
