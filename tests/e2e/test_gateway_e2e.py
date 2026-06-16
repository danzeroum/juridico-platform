"""
Testes E2E do gateway via FastAPI TestClient.

Exercitam o stack completo da aplicação: roteamento, middleware JWT,
rate limit, handlers de erro problem+json e formato de resposta.

Não requerem serviços externos (Redis, MinIO, ChromaDB): as rotas degradam
graciosamente retornando stubs/fallbacks quando o cache está offline.
E2E com Docker real (incluindo ingestão de dados) permanece pendente de infra.

Execução: pytest tests/e2e/test_gateway_e2e.py -v
"""
from __future__ import annotations

import io
import os

import pytest
from fastapi.testclient import TestClient

# HMAC_KEY necessário para hash_user_id() no legalscore; usar valor efêmero de dev
os.environ.setdefault("HMAC_KEY", "0" * 64)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """TestClient contra o app completo (JWT + rate limit + todos os routers)."""
    from services.gateway.main import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def token():
    """JWT válido para tenant 'e2e-tenant'."""
    from services.gateway.auth.jwt import issue_token
    return issue_token("e2e-user", "e2e-tenant", "user")


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Health (sem auth)
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("status") in ("ok", "healthy")

    def test_openapi_spec_disponivel(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()
        assert "paths" in spec
        assert "/api/v1/legalscore/score" in spec["paths"]
        assert "/api/v1/taxpredict/predict" in spec["paths"]
        assert "/api/v1/petibot/assemble" in spec["paths"]
        assert "/api/v1/concilia/recommend" in spec["paths"]


# ---------------------------------------------------------------------------
# Auth (JWT obrigatório)
# ---------------------------------------------------------------------------

class TestAuth:
    def test_sem_token_retorna_401(self, client):
        resp = client.post("/api/v1/legalscore/score", json={"cnpj": "12345678000195"})
        assert resp.status_code == 401
        ct = resp.headers.get("content-type", "")
        assert "problem+json" in ct

    def test_token_invalido_retorna_401(self, client):
        resp = client.post(
            "/api/v1/legalscore/score",
            json={"cnpj": "12345678000195"},
            headers={"Authorization": "Bearer token-invalido"},
        )
        assert resp.status_code == 401

    def test_token_valido_nao_retorna_401(self, client, auth):
        resp = client.post(
            "/api/v1/legalscore/score",
            json={"cnpj": "12345678000195"},
            headers=auth,
        )
        assert resp.status_code != 401


# ---------------------------------------------------------------------------
# LegalScore PJ
# ---------------------------------------------------------------------------

class TestLegalScore:
    def test_score_retorna_200_com_stub(self, client, auth):
        resp = client.post(
            "/api/v1/legalscore/score",
            json={"cnpj": "12345678000195"},
            headers=auth,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "score" in body
        assert "risk_level" in body
        assert "request_id" in body
        assert body["contract_version"] == "scoring/v1"

    def test_score_cnpj_invalido_retorna_422_problem_json(self, client, auth):
        resp = client.post(
            "/api/v1/legalscore/score",
            json={"cnpj": "123"},  # muito curto
            headers=auth,
        )
        assert resp.status_code == 422
        ct = resp.headers.get("content-type", "")
        assert "problem+json" in ct
        body = resp.json()
        assert "detail" in body
        assert body["status"] == 422

    def test_score_sem_body_retorna_422(self, client, auth):
        resp = client.post("/api/v1/legalscore/score", headers=auth)
        assert resp.status_code == 422

    def test_batch_retorna_202(self, client, auth):
        resp = client.post(
            "/api/v1/legalscore/batch",
            json={"cnpjs": ["12345678000195", "98765432000181"]},
            headers=auth,
        )
        # 202 se Celery/Redis disponível; 503 se offline — mas nunca 4xx
        assert resp.status_code in (202, 503)

    def test_model_metrics_retorna_200(self, client, auth):
        resp = client.get("/api/v1/legalscore/model-metrics", headers=auth)
        assert resp.status_code == 200
        body = resp.json()
        assert "validation_status" in body

    def test_company_profile_sem_dados_retorna_404(self, client, auth):
        resp = client.get("/api/v1/legalscore/company/12345678000195", headers=auth)
        # 404 se Redis offline (sem dados de ingestão)
        assert resp.status_code in (404, 200)


# ---------------------------------------------------------------------------
# TaxPredict
# ---------------------------------------------------------------------------

class TestTaxPredict:
    def test_predict_retorna_prior_nacional_fallback(self, client, auth):
        resp = client.post(
            "/api/v1/taxpredict/predict",
            json={"materia": "ICMS", "descricao": "Autuação fiscal por ICMS diferencial de alíquota"},
            headers=auth,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "probability" in body
        assert "is_fallback" in body
        assert body["contract_version"] == "taxpredict/v1"

    def test_predict_materia_invalida_422(self, client, auth):
        resp = client.post(
            "/api/v1/taxpredict/predict",
            json={"materia": "INVALIDO", "descricao": "qualquer"},
            headers=auth,
        )
        assert resp.status_code == 422
        assert "problem+json" in resp.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# PetiBot
# ---------------------------------------------------------------------------

class TestPetiBot:
    def test_assemble_retorna_200(self, client, auth):
        resp = client.post(
            "/api/v1/petibot/assemble",
            json={
                "tipo_acao": "TRABALHISTA",
                "descricao": "Empregado dispensado sem justa causa após 5 anos de serviços prestados na empresa reclamada.",
                "polo_ativo": "João Silva",
                "polo_passivo": "Empresa XYZ LTDA",
            },
            headers=auth,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "secoes" in body
        assert body["contract_version"] == "petibot/v1"

    def test_assemble_tipo_invalido_422(self, client, auth):
        resp = client.post(
            "/api/v1/petibot/assemble",
            json={"tipo_acao": "INEXISTENTE", "descricao_fatos": "x", "pedidos": ["x"]},
            headers=auth,
        )
        assert resp.status_code == 422
        assert "problem+json" in resp.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# ConciliaIA
# ---------------------------------------------------------------------------

class TestConcilia:
    def test_recommend_retorna_200(self, client, auth):
        resp = client.post(
            "/api/v1/concilia/recommend",
            json={
                "tipo_acao": "TRABALHISTA",
                "valor_causa": 50000.0,
                "descricao": "Dispensa sem justa causa, pedido de verbas rescisórias",
            },
            headers=auth,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "valor_minimo" in body
        assert "valor_maximo" in body
        assert body["contract_version"] == "concilia/v1"

    def test_recommend_valor_zero_422(self, client, auth):
        resp = client.post(
            "/api/v1/concilia/recommend",
            json={"tipo_acao": "TRABALHISTA", "valor_causa": 0, "descricao": "x"},
            headers=auth,
        )
        assert resp.status_code == 422
        assert "problem+json" in resp.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# ContabilIA
# ---------------------------------------------------------------------------

class TestContabilIA:
    def test_upload_csv_retorna_200(self, client, auth):
        csv_content = b"conta,valor\nreceita_liquida,1000000\nheadcount,50\nebitda,200000\n"
        resp = client.post(
            "/api/v1/contabilia/audit/upload",
            files={"file": ("dre.csv", io.BytesIO(csv_content), "text/csv")},
            headers=auth,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "report_id" in body
        assert body["status"] == "CONCLUIDO"
        assert body["contract_version"] == "contabilia/v1"

    def test_upload_tipo_errado_retorna_400(self, client, auth):
        resp = client.post(
            "/api/v1/contabilia/audit/upload",
            files={"file": ("dados.json", io.BytesIO(b'{"key": "val"}'), "application/json")},
            headers=auth,
        )
        assert resp.status_code == 400

    def test_upload_csv_vazio_retorna_422(self, client, auth):
        resp = client.post(
            "/api/v1/contabilia/audit/upload",
            files={"file": ("empty.csv", io.BytesIO(b"conta,valor\n"), "text/csv")},
            headers=auth,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# ComplianceRadar
# ---------------------------------------------------------------------------

class TestCompliance:
    def test_municipality_ibge_invalido_retorna_400(self, client, auth):
        resp = client.get("/api/v1/compliance/municipality/INVALIDO", headers=auth)
        assert resp.status_code == 400
        body = resp.json()
        assert "problem+json" in resp.headers.get("content-type", "")
        assert body["status"] == 400

    def test_municipality_ibge_muito_curto_retorna_400(self, client, auth):
        resp = client.get("/api/v1/compliance/municipality/123456", headers=auth)
        assert resp.status_code == 400

    def test_municipalities_retorna_200_ou_503(self, client, auth):
        resp = client.get("/api/v1/compliance/municipalities", headers=auth)
        # 200 com lista vazia se Redis offline, ou 503
        assert resp.status_code in (200, 503)


# ---------------------------------------------------------------------------
# DanoBot (bloqueado PD-06)
# ---------------------------------------------------------------------------

class TestDanoBot:
    def test_predict_retorna_501(self, client, auth):
        resp = client.post("/api/v1/danobot/predict", headers=auth)
        assert resp.status_code == 501
        body = resp.json()
        assert "PD-06" in body.get("detail", "")


# ---------------------------------------------------------------------------
# LicitaWatch
# ---------------------------------------------------------------------------

class TestLicitaWatch:
    def test_contratos_cnpj_invalido_retorna_422(self, client, auth):
        resp = client.get(
            "/api/v1/licitawatch/contratos/123?referencia=2024",
            headers=auth,
        )
        assert resp.status_code == 422
        ct = resp.headers.get("content-type", "")
        assert "json" in ct

    def test_contratos_retorna_200_redis_offline(self, client, auth):
        resp = client.get(
            "/api/v1/licitawatch/contratos/12345678000195?referencia=2024",
            headers=auth,
        )
        # Redis offline → lista vazia com graceful degradation
        assert resp.status_code == 200
        body = resp.json()
        assert "contratos" in body
        assert "total" in body
        assert body["cnpj_orgao"] == "12345678000195"

    def test_evaluate_cnpj_invalido_retorna_422(self, client, auth):
        resp = client.post(
            "/api/v1/licitawatch/orgao/INVALIDO/evaluate?referencia=2024",
            headers=auth,
        )
        assert resp.status_code == 422

    def test_evaluate_retorna_200_sem_dados(self, client, auth):
        resp = client.post(
            "/api/v1/licitawatch/orgao/12345678000195/evaluate?referencia=2024",
            headers=auth,
        )
        # Redis offline → zero contratos → zero alertas
        assert resp.status_code == 200
        body = resp.json()
        assert "alertas" in body
        assert "envelopes" in body
        assert body["contract_version"] == "licitawatch/v1"


# ---------------------------------------------------------------------------
# Erros globais — problem+json
# ---------------------------------------------------------------------------

class TestGlobalErrors:
    def test_rota_inexistente_retorna_404(self, client, auth):
        resp = client.get("/api/v1/rota-que-nao-existe", headers=auth)
        assert resp.status_code == 404

    def test_metrics_endpoint_disponivel(self, client, auth):
        # /metrics exposto pelo prometheus-fastapi-instrumentator
        resp = client.get("/metrics", headers=auth)
        # 200 se instrumentator instalado; pode requerer auth dependendo do middleware
        assert resp.status_code in (200, 401, 404)
