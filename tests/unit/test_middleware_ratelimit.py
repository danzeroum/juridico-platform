"""
Testes de rate limiting por tenant (P0-4 da DoD).

Usa um app FastAPI mínimo com apenas o RateLimitMiddleware para isolar
o comportamento sem depender do stack completo (JWT, banco, etc.).
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import services.gateway.middleware as mw_module
from services.gateway.middleware import RateLimitMiddleware


def _make_app(tenant_id: str = "test-tenant") -> tuple[FastAPI, TestClient]:
    """Cria app mínimo com RateLimitMiddleware; injeta tenant_id no state."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.middleware("http")
    async def inject_tenant(request, call_next):
        request.state.tenant_id = tenant_id
        return await call_next(request)

    @app.get("/ping")
    def ping():
        return JSONResponse({"ok": True})

    return app, TestClient(app, raise_server_exceptions=False)


def _reset_counts() -> None:
    """Limpa o contador global entre testes (isolamento)."""
    mw_module._request_counts.clear()


class TestRateLimit:
    def setup_method(self):
        _reset_counts()

    def test_primeiras_100_requests_retornam_200(self):
        _, client = _make_app()
        for _ in range(100):
            resp = client.get("/ping")
            assert resp.status_code == 200

    def test_101a_request_retorna_429(self, monkeypatch):
        monkeypatch.setattr(mw_module.time, "time", lambda: 0.0)
        _reset_counts()
        _, client = _make_app()
        for _ in range(100):
            client.get("/ping")
        resp = client.get("/ping")
        assert resp.status_code == 429

    def test_resposta_429_e_problem_json(self, monkeypatch):
        monkeypatch.setattr(mw_module.time, "time", lambda: 0.0)
        _reset_counts()
        _, client = _make_app()
        for _ in range(101):
            resp = client.get("/ping")
        assert resp.headers.get("content-type", "").startswith("application/problem+json")
        body = resp.json()
        assert body["status"] == 429
        assert "type" in body
        assert "detail" in body

    def test_429_tem_retry_after(self, monkeypatch):
        monkeypatch.setattr(mw_module.time, "time", lambda: 0.0)
        _reset_counts()
        _, client = _make_app()
        for _ in range(101):
            resp = client.get("/ping")
        assert "Retry-After" in resp.headers
        assert resp.headers["Retry-After"] == "60"

    def test_tenant_a_nao_afeta_tenant_b(self, monkeypatch):
        """Rate limit é por tenant, não global."""
        monkeypatch.setattr(mw_module.time, "time", lambda: 0.0)
        _reset_counts()
        _, client_a = _make_app(tenant_id="tenant-a")
        _, client_b = _make_app(tenant_id="tenant-b")

        # Enche o limite de A
        for _ in range(101):
            client_a.get("/ping")
        assert client_a.get("/ping").status_code == 429

        # B ainda está no limite
        assert client_b.get("/ping").status_code == 200

    def test_janela_de_tempo_reseta_contador(self, monkeypatch):
        """Counter é por minuto: nova janela = novo contador."""
        _, client = _make_app()

        # Simula minuto 1: enche o limite
        monkeypatch.setattr(mw_module.time, "time", lambda: 0.0)
        _reset_counts()
        for _ in range(101):
            client.get("/ping")
        assert client.get("/ping").status_code == 429

        # Simula minuto 2: counter reset (chave nova)
        monkeypatch.setattr(mw_module.time, "time", lambda: 60.0)
        assert client.get("/ping").status_code == 200
