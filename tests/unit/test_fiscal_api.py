"""
Testes de API dos endpoints do FiscalEngine via FastAPI TestClient.

Exercita o roteador (services/gateway/routers/fiscal.py) de ponta a ponta no nível
HTTP — validação, códigos de status, formato de resposta — com as dependências de
infra (Postgres/Ledger/MinIO/Celery) faked. Complementa os testes de unidade do
motor; o E2E full-stack (Postgres+Redis+MinIO+Chromium+Ollama) permanece um gate de
DoD não executável na CI atual.
"""
from __future__ import annotations

import io

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from openpyxl import Workbook

from services.gateway.routers import fiscal as fiscal_router
from services.shared.contracts.fiscal import (
    FonteRegra,
    IcmsResolution,
    NcmCandidate,
    NcmTriageResult,
)
from services.shared.ledger.merkle import DecisionLedger

TENANT = "00000000-0000-0000-0000-0000000000aa"


def _fake_result(descricao: str) -> NcmTriageResult:
    return NcmTriageResult(
        sku_descricao=descricao,
        suggested_ncm=NcmCandidate(
            ncm_codigo="84713012", descricao="Notebook", confidence=1.0, fonte_regra=FonteRegra.TIPI
        ),
        icms=IcmsResolution(interna_efetiva_pct=20.0, interestadual_pct=12.0, difal_pct=8.0),
    )


def _app(with_tenant: bool = True) -> FastAPI:
    app = FastAPI()
    if with_tenant:
        @app.middleware("http")
        async def _inject_tenant(request: Request, call_next):
            request.state.tenant_id = TENANT
            return await call_next(request)
    app.include_router(fiscal_router.router, prefix="/api/v1/fiscal")
    return app


@pytest.fixture
def client(monkeypatch):
    # Fake do classify (evita Postgres) e do Ledger (em memória, sem DB).
    monkeypatch.setattr(fiscal_router, "classify_one", lambda req: _fake_result(req.descricao))
    monkeypatch.setattr(fiscal_router, "_get_ledger", lambda tid: DecisionLedger())
    return TestClient(_app())


class TestTriage:
    def test_triage_200_com_prova(self, client):
        r = client.post(
            "/api/v1/fiscal/ncm/triage",
            json={"descricao": "Notebook Dell", "uf_origem": "SP", "uf_destino": "RJ", "ncm_hint": "84713012"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["suggested_ncm"]["ncm_codigo"] == "84713012"
        assert body["icms"]["difal_pct"] == 8.0
        assert body["decision_proof"]  # preenchido pela ancoragem no Ledger

    def test_triage_sem_tenant_401(self, monkeypatch):
        monkeypatch.setattr(fiscal_router, "classify_one", lambda req: _fake_result(req.descricao))
        c = TestClient(_app(with_tenant=False))
        r = c.post(
            "/api/v1/fiscal/ncm/triage",
            json={"descricao": "x", "uf_origem": "SP", "uf_destino": "RJ"},
        )
        assert r.status_code == 401

    def test_triage_payload_invalido_422(self, client):
        r = client.post("/api/v1/fiscal/ncm/triage", json={"descricao": "x", "uf_origem": "ZZ"})
        assert r.status_code == 422  # UF inválida / campo faltando


class TestValidacaoSemDB:
    def test_icms_uf_invalida_400(self, client):
        r = client.get("/api/v1/fiscal/icms/84713012/ZZ")
        assert r.status_code == 400

    def test_ncm_codigo_invalido_400(self, client):
        r = client.get("/api/v1/fiscal/ncm/123")
        assert r.status_code == 400


class TestEnrich:
    def _xlsx(self) -> bytes:
        wb = Workbook()
        ws = wb.active
        ws.append(["Descrição", "NCM", "UF"])
        ws.append(["Notebook Dell", "8471.30.12", "RJ"])
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def test_enrich_202(self, client, monkeypatch):
        import celery

        monkeypatch.setattr("services.fiscal.storage.upload_spreadsheet", lambda key, data: key)
        monkeypatch.setattr(celery.current_app, "send_task", lambda *a, **k: None)

        r = client.post(
            "/api/v1/fiscal/spreadsheet/enrich",
            files={"file": ("itens.xlsx", self._xlsx(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert r.status_code == 202
        body = r.json()
        assert body["job_id"].startswith("fiscal_")
        assert body["status_url"].endswith(body["job_id"])

    def test_enrich_uf_origem_invalida_400(self, client):
        r = client.post(
            "/api/v1/fiscal/spreadsheet/enrich?uf_origem=ZZ",
            files={"file": ("itens.xlsx", self._xlsx(), "application/octet-stream")},
        )
        assert r.status_code == 400
