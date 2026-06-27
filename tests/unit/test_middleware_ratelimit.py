"""
Testes de rate limiting por tenant (agora via Redis INCR + TTL).

Usa um app FastAPI mínimo com apenas o RateLimitMiddleware e um Redis falso
em memória (injetado no lugar de get_redis), para exercitar o comportamento
sem depender de um Redis real.
"""
from __future__ import annotations

import sys
import types

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import services.gateway.middleware as mw_module
from services.gateway.middleware import RateLimitMiddleware


class FakeRedis:
    """Redis em memória mínimo: incr/expire — suficiente para o limiter."""

    def __init__(self) -> None:
        self.store: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    def expire(self, key: str, ttl: int) -> None:  # noqa: ARG002
        pass


class BrokenRedis:
    """Simula Redis fora do ar (toda operação levanta)."""

    def incr(self, key: str) -> int:
        raise ConnectionError("redis down")

    def expire(self, key: str, ttl: int) -> None:
        raise ConnectionError("redis down")


@pytest.fixture(autouse=True)
def redis_holder():
    """
    Injeta um módulo falso `services.shared.redis_client` em sys.modules (o
    middleware faz `from services.shared.redis_client import get_redis` de forma
    lazy). Evita importar o módulo real — que, fora do contexto de runtime,
    falha em `from shared.config import settings`. Também zera o circuit breaker.
    """
    holder = {"client": FakeRedis()}
    mod = types.ModuleType("services.shared.redis_client")
    mod.get_redis = lambda: holder["client"]
    saved = sys.modules.get("services.shared.redis_client")
    sys.modules["services.shared.redis_client"] = mod
    mw_module._redis_down_until = 0.0
    yield holder
    mw_module._redis_down_until = 0.0
    if saved is not None:
        sys.modules["services.shared.redis_client"] = saved
    else:
        sys.modules.pop("services.shared.redis_client", None)


def _make_app(tenant_id: str = "test-tenant") -> TestClient:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.middleware("http")
    async def inject_tenant(request, call_next):
        request.state.tenant_id = tenant_id
        return await call_next(request)

    @app.get("/ping")
    def ping():
        return JSONResponse({"ok": True})

    return TestClient(app, raise_server_exceptions=False)


class TestRateLimit:
    def test_primeiras_100_requests_retornam_200(self):
        client = _make_app()
        for _ in range(100):
            assert client.get("/ping").status_code == 200

    def test_101a_request_retorna_429(self, monkeypatch):
        monkeypatch.setattr(mw_module.time, "time", lambda: 0.0)
        client = _make_app()
        for _ in range(100):
            client.get("/ping")
        assert client.get("/ping").status_code == 429

    def test_resposta_429_e_problem_json(self, monkeypatch):
        monkeypatch.setattr(mw_module.time, "time", lambda: 0.0)
        client = _make_app()
        resp = None
        for _ in range(101):
            resp = client.get("/ping")
        assert resp.headers.get("content-type", "").startswith("application/problem+json")
        body = resp.json()
        assert body["status"] == 429
        assert "type" in body and "detail" in body

    def test_429_tem_retry_after(self, monkeypatch):
        monkeypatch.setattr(mw_module.time, "time", lambda: 0.0)
        client = _make_app()
        resp = None
        for _ in range(101):
            resp = client.get("/ping")
        assert resp.headers.get("Retry-After") == "60"

    def test_tenant_a_nao_afeta_tenant_b(self, monkeypatch):
        monkeypatch.setattr(mw_module.time, "time", lambda: 0.0)
        client_a = _make_app(tenant_id="tenant-a")  # store do FakeRedis é compartilhado
        client_b = _make_app(tenant_id="tenant-b")
        for _ in range(101):
            client_a.get("/ping")
        assert client_a.get("/ping").status_code == 429
        assert client_b.get("/ping").status_code == 200

    def test_janela_de_tempo_reseta_contador(self, monkeypatch):
        client = _make_app()
        monkeypatch.setattr(mw_module.time, "time", lambda: 0.0)
        for _ in range(101):
            client.get("/ping")
        assert client.get("/ping").status_code == 429
        # Minuto seguinte: chave nova → contador zera.
        monkeypatch.setattr(mw_module.time, "time", lambda: 60.0)
        assert client.get("/ping").status_code == 200


class TestRedisIndisponivel:
    def test_fail_open_por_padrao(self, monkeypatch, redis_holder):
        """Redis fora → fail-open: requests passam (disponibilidade preservada)."""
        monkeypatch.setattr(mw_module, "_RATE_LIMIT_FAIL_CLOSED", False)
        redis_holder["client"] = BrokenRedis()
        client = _make_app()
        assert client.get("/ping").status_code == 200

    def test_fail_closed_quando_configurado(self, monkeypatch, redis_holder):
        """Com RATE_LIMIT_FAIL_CLOSED, Redis fora → 503."""
        monkeypatch.setattr(mw_module, "_RATE_LIMIT_FAIL_CLOSED", True)
        redis_holder["client"] = BrokenRedis()
        client = _make_app()
        resp = client.get("/ping")
        assert resp.status_code == 503
        assert resp.headers.get("content-type", "").startswith("application/problem+json")
