"""
Testes do handler global de erros problem+json (RFC 9457).

Garante que TODOS os erros da API retornam application/problem+json:
- HTTPException genérica (string detail)
- HTTPException com dict detail já formatado (sem double-wrap)
- RequestValidationError (Pydantic 422) — antes retornava default FastAPI
- Erro interno (500)
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel


class _ValidateBody(BaseModel):
    name: str
    age: int


def _make_handler_app() -> tuple[FastAPI, TestClient]:
    """App mínimo que instala os handlers de main.py mas sem middlewares JWT/rate-limit."""
    from services.gateway.main import _problem_json  # noqa: PLC0415

    app = FastAPI()

    @app.get("/test/ibge-error")
    def ibge_error():
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://juridico.io/errors/ibge-invalido",
                "title": "Código IBGE inválido",
                "status": 400,
                "detail": "cod_ibge deve conter exatamente 7 dígitos numéricos.",
                "instance": "/api/v1/test",
                "contract_version": "compliance/v1",
            },
        )

    @app.get("/test/string-error")
    def string_error():
        raise HTTPException(status_code=404, detail="Não encontrado.")

    @app.get("/test/server-error")
    def server_error():
        raise RuntimeError("boom")

    @app.post("/test/validate")
    def validate(body: _ValidateBody) -> JSONResponse:
        return JSONResponse({"ok": True})

    @app.post("/test/danobot-block")
    def danobot():
        raise HTTPException(
            status_code=501,
            detail={
                "type": "https://juridico.io/errors/danobot/blocked",
                "title": "DanoBot bloqueado",
                "status": 501,
                "detail": "Requer parecer DPO.",
                "instance": "/api/v1/danobot/predict",
                "contract_version": "danobot/v1",
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exc(request, exc):
        return _problem_json(exc.status_code, exc.detail, str(request.url.path))

    @app.exception_handler(RequestValidationError)
    async def val_exc(request, exc):
        errors = exc.errors()
        detail = "; ".join(
            f"{' → '.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in errors
        )
        return _problem_json(422, detail, str(request.url.path),
                             type_suffix="validation-error", title="Erro de validação")

    @app.exception_handler(Exception)
    async def generic_exc(request, exc):
        return _problem_json(500,
                             "Erro interno.",
                             str(request.url.path))

    return app, TestClient(app, raise_server_exceptions=False)


_app, _client = _make_handler_app()


# ---------------------------------------------------------------------------
# HTTPException → problem+json
# ---------------------------------------------------------------------------

def test_string_detail_is_problem_json():
    resp = _client.get("/test/string-error")
    assert resp.status_code == 404
    ct = resp.headers.get("content-type", "")
    assert ct.startswith("application/problem+json")
    body = resp.json()
    assert body["status"] == 404
    assert body["detail"] == "Não encontrado."
    assert "type" in body and "title" in body and "instance" in body


def test_string_detail_has_all_required_fields():
    resp = _client.get("/test/string-error")
    body = resp.json()
    for field in ("type", "title", "status", "detail", "instance"):
        assert field in body, f"Campo obrigatório ausente: {field!r}"


# ---------------------------------------------------------------------------
# Dict detail sem double-wrap
# ---------------------------------------------------------------------------

def test_dict_detail_not_double_wrapped():
    """Se detail já é problem+json completo, não deve ser envolto novamente."""
    resp = _client.get("/test/ibge-error")
    assert resp.status_code == 400
    body = resp.json()
    # O body DEVE ter "type" diretamente (não dentro de "detail")
    assert "type" in body
    assert body["type"] == "https://juridico.io/errors/ibge-invalido"
    # "detail" deve ser string, não dict aninhado com type/title/status
    assert isinstance(body["detail"], str), (
        f"double-wrap: detail é {type(body['detail'])!r}: {body['detail']}"
    )


def test_dict_detail_passes_through_as_is():
    resp = _client.post("/test/danobot-block")
    assert resp.status_code == 501
    body = resp.json()
    assert body["type"] == "https://juridico.io/errors/danobot/blocked"
    assert body["title"] == "DanoBot bloqueado"
    assert body["contract_version"] == "danobot/v1"


# ---------------------------------------------------------------------------
# RequestValidationError (422) → problem+json
# ---------------------------------------------------------------------------

def test_pydantic_422_is_problem_json():
    resp = _client.post("/test/validate", json={"name": "ok"})  # age ausente
    assert resp.status_code == 422
    ct = resp.headers.get("content-type", "")
    assert ct.startswith("application/problem+json"), (
        f"422 não retornou problem+json: content-type={ct!r} body={resp.text}"
    )


def test_pydantic_422_has_required_fields():
    resp = _client.post("/test/validate", json={"name": "ok"})
    body = resp.json()
    for field in ("type", "title", "status", "detail", "instance"):
        assert field in body, f"Campo obrigatório ausente em 422: {field!r}"
    assert body["status"] == 422
    assert "age" in body["detail"].lower()


def test_pydantic_422_type_suffix():
    resp = _client.post("/test/validate", json={})
    body = resp.json()
    assert "validation-error" in body["type"]


# ---------------------------------------------------------------------------
# Erro interno (500) → problem+json
# ---------------------------------------------------------------------------

def test_server_error_is_problem_json():
    resp = _client.get("/test/server-error")
    assert resp.status_code == 500
    ct = resp.headers.get("content-type", "")
    assert ct.startswith("application/problem+json")
    body = resp.json()
    assert body["status"] == 500


# ---------------------------------------------------------------------------
# _status_title
# ---------------------------------------------------------------------------

def test_status_title_503():
    from services.gateway.main import _status_title
    assert _status_title(503) == "Serviço indisponível"


def test_status_title_known_codes():
    from services.gateway.main import _status_title
    assert _status_title(400) == "Requisição inválida"
    assert _status_title(401) == "Não autenticado"
    assert _status_title(404) == "Recurso não encontrado"
    assert _status_title(429) == "Rate limit excedido"


def test_status_title_unknown_fallback():
    from services.gateway.main import _status_title
    assert _status_title(999) == "Erro"
