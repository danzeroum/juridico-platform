"""
Gateway principal — juridico-platform.

Endpoint de referência (P2 compliance completo):
  POST /api/v1/legalscore/score
    - JWT RS256 (via JWTAuthMiddleware)
    - Rate limit por tenant (via RateLimitMiddleware)
    - Idempotency-Key (24h, retry-safety only)
    - problem+json em todos os erros
    - OTel span por request
    - OpenAPI 3.1 com exemplos reais

Todos os outros endpoints seguem este padrão.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from services.gateway.middleware import (
    JWTAuthMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)

# OTel — graceful degradation se SDK não instalado
try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False
    trace = None  # type: ignore[assignment]

# Prometheus
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    _PROM_AVAILABLE = True
except ImportError:
    _PROM_AVAILABLE = False

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Setup de observabilidade no startup."""
    _setup_logging()
    _setup_otel()
    _setup_prometheus(app)
    logger.info("Gateway iniciado. Versão 0.2.0")
    yield
    logger.info("Gateway encerrando.")


def _setup_logging() -> None:
    import json
    import sys

    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            log = {
                "level": record.levelname,
                "name": record.name,
                "message": record.getMessage(),
                "timestamp": self.formatTime(record),
            }
            if record.exc_info:
                log["exc_info"] = self.formatException(record.exc_info)
            return json.dumps(log, ensure_ascii=False)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]


def _setup_otel() -> None:
    if not _OTEL_AVAILABLE:
        logger.warning("OpenTelemetry não instalado — tracing desabilitado.")
        return
    import os
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if not endpoint:
        logger.info("OTEL_EXPORTER_OTLP_ENDPOINT não configurado — tracing local apenas.")
        provider = TracerProvider()
    else:
        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)


def _setup_prometheus(app: FastAPI) -> None:
    if not _PROM_AVAILABLE:
        logger.warning("prometheus-fastapi-instrumentator não instalado — métricas desabilitadas.")
        return
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")


app = FastAPI(
    title="juridico-platform-gateway",
    version="0.2.0",
    description="Gateway de API — Plataforma Jurídico-Contábil",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Middlewares (ordem: externo → interno)
app.add_middleware(JWTAuthMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Registrar routers dos produtos
from services.gateway.routers import (  # noqa: E402
    auth,
    compliance,
    concilia,
    contabilia,
    danobot,
    defensor,
    entidade,
    health,
    legalscore,
    licitawatch,
    petibot,
    taxpredict,
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(legalscore.router, prefix="/api/v1/legalscore")
app.include_router(contabilia.router, prefix="/api/v1/contabilia")
app.include_router(compliance.router, prefix="/api/v1/compliance")
app.include_router(taxpredict.router, prefix="/api/v1/taxpredict")
app.include_router(licitawatch.router, prefix="/api/v1/licitawatch")
app.include_router(petibot.router, prefix="/api/v1/petibot")
app.include_router(danobot.router, prefix="/api/v1/danobot")
app.include_router(concilia.router, prefix="/api/v1/concilia")
app.include_router(defensor.router, prefix="/api/v1/defensor")
app.include_router(entidade.router, prefix="/api/v1/entidade")


# ---------------------------------------------------------------------------
# Raiz
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def root() -> JSONResponse:
    return JSONResponse({
        "name": "juridico-platform-gateway",
        "version": "0.2.0",
        "docs": "/docs",
    })


# ---------------------------------------------------------------------------
# JWKS — chave pública para validação externa de tokens
# ---------------------------------------------------------------------------
@app.get("/.well-known/jwks.json", include_in_schema=False)
def jwks() -> JSONResponse:
    try:
        import base64

        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        from services.gateway.auth.jwt import get_public_key_pem

        pub_pem = get_public_key_pem().encode()
        pub_key = load_pem_public_key(pub_pem)
        pub_numbers = pub_key.public_key().public_numbers()  # type: ignore[union-attr]

        def _b64url(n: int) -> str:
            length = (n.bit_length() + 7) // 8
            return base64.urlsafe_b64encode(n.to_bytes(length, "big")).rstrip(b"=").decode()

        return JSONResponse({
            "keys": [{
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "n": _b64url(pub_numbers.n),
                "e": _b64url(pub_numbers.e),
            }]
        })
    except Exception:
        from services.gateway.auth.jwt import get_public_key_pem
        return JSONResponse({"keys": [{"kty": "RSA", "use": "sig", "alg": "RS256", "pem": get_public_key_pem()}]})


# ---------------------------------------------------------------------------
# Handlers globais de erros → application/problem+json (RFC 9457)
# ---------------------------------------------------------------------------
def _problem_json(
    status_code: int,
    detail: object,
    instance: str,
    *,
    type_suffix: str | None = None,
    title: str | None = None,
) -> JSONResponse:
    """Constrói resposta application/problem+json a partir de qualquer detalhe.

    Se `detail` já é um dict problem+json completo (tem type+title+status),
    passa-o diretamente para evitar double-wrapping.
    """
    if (
        isinstance(detail, dict)
        and "type" in detail
        and "title" in detail
        and "status" in detail
    ):
        body = detail
        if "instance" not in body:
            body = {**body, "instance": instance}
    else:
        body = {
            "type": f"https://juridico-platform/errors/{type_suffix or status_code}",
            "title": title or _status_title(status_code),
            "status": status_code,
            "detail": detail,
            "instance": instance,
            "contract_version": "1.0",
        }
    return JSONResponse(
        status_code=status_code,
        content=body,
        headers={"Content-Type": "application/problem+json"},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return _problem_json(exc.status_code, exc.detail, str(request.url.path))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    detail = "; ".join(
        f"{' → '.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in errors
    )
    return _problem_json(
        422,
        detail,
        str(request.url.path),
        type_suffix="validation-error",
        title="Erro de validação",
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Erro interno em %s", request.url.path)
    return _problem_json(
        500,
        "Ocorreu um erro interno. Tente novamente ou contate o suporte.",
        str(request.url.path),
    )


def _status_title(status: int) -> str:
    return {
        400: "Requisição inválida",
        401: "Não autenticado",
        402: "Pagamento necessário",
        403: "Não autorizado",
        404: "Recurso não encontrado",
        409: "Conflito",
        422: "Entidade não processável",
        429: "Rate limit excedido",
        500: "Erro interno do servidor",
        501: "Não implementado",
        503: "Serviço indisponível",
    }.get(status, "Erro")
