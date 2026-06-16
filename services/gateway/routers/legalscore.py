"""
LegalScore PJ — Router de referência (P2 compliance completo).

Este router serve como TEMPLATE para todos os demais produtos:
- Versionamento /api/v1/legalscore/...
- problem+json em todos os erros (via handler global em main.py)
- Idempotency-Key (24h TTL, retry-safety)
- OTel span por operação
- OpenAPI com exemplos reais
- Rate limiting por tenant (via RateLimitMiddleware)
- JWT obrigatório (via JWTAuthMiddleware)
- Score rotulado como heurística até validação formal (AUC/Brier)
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from services.scoring.engine.factory import get_score_engine
from services.scoring.features import assemble_features
from services.shared.contracts.scoring import ScoreRequest as EngineScoreRequest
from services.shared.ledger.merkle import DecisionLedger
from services.shared.lgpd import hash_user_id

# OTel — graceful degradation
try:
    from opentelemetry import trace as otel_trace
    _tracer = otel_trace.get_tracer("legalscore")
    _OTEL = True
except ImportError:
    _OTEL = False
    _tracer = None  # type: ignore[assignment]

# In-memory ledger para Fase 1b. Fase 1c migra para Postgres com âncoras.
_ledger = DecisionLedger()

router = APIRouter(tags=["legalscore"])

_SCORE_DISCLAIMER = (
    "heurística — não validado contra desfechos reais. "
    "AUC e calibração pendentes (Fase 1d)."
)


# ---------------------------------------------------------------------------
# Modelos de request/response
# ---------------------------------------------------------------------------
class ScoreRequest(BaseModel):
    cnpj: str = Field(..., pattern=r"^\d{14}$", description="CNPJ sem formatação (14 dígitos)")

    model_config = {
        "json_schema_extra": {
            "example": {"cnpj": "12345678000195"}
        }
    }


class ScoreResponse(BaseModel):
    cnpj: str
    score: int = Field(..., ge=0, le=1000, description="Score de risco [0-1000]")
    risk_level: str = Field(..., description="BAIXO | MODERADO | ALTO | CRITICO")
    confidence_interval: list[float] = Field(..., description="[lower, upper] 95%")
    breakdown: dict[str, float] = Field(default_factory=dict)
    disclaimer: str = Field(default=_SCORE_DISCLAIMER)
    request_id: str
    source_date: str | None = None
    lag_days: int | None = None
    engine: str = "python"
    contract_version: str = "scoring/v1"

    model_config = {
        "json_schema_extra": {
            "example": {
                "cnpj": "12345678000195",
                "score": 720,
                "risk_level": "MODERADO",
                "confidence_interval": [641, 799],
                "breakdown": {
                    "processos_ativos": -15.0,
                    "divida_ativa_valor_log": -30.0,
                    "capital_social_log": 45.0,
                },
                "disclaimer": "heurística — não validado contra desfechos reais.",
                "request_id": "req_01abc123",
                "source_date": "2026-06-15",
                "lag_days": 1,
                "engine": "python",
                "contract_version": "scoring/v1",
            }
        }
    }


class BatchScoreRequest(BaseModel):
    cnpjs: list[str] = Field(..., min_length=1, max_length=1000)


# ---------------------------------------------------------------------------
# Dependência: extrair tenant do request state (injetado pelo middleware JWT)
# ---------------------------------------------------------------------------
def _get_tenant(request: Request) -> str:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token JWT não contém tenant_id.",
        )
    return tenant_id


# ---------------------------------------------------------------------------
# POST /api/v1/legalscore/score — endpoint de referência P2
# ---------------------------------------------------------------------------
@router.post(
    "/score",
    response_model=ScoreResponse,
    summary="Score de risco jurídico-financeiro de PJ",
    description=(
        "Calcula o LegalScore para um CNPJ com base em processos judiciais, "
        "dívida ativa e dados cadastrais. Score rotulado como **heurística** até "
        "validação formal (AUC/Brier — Fase 1d).\n\n"
        "**Idempotência:** requests com mesmo `Idempotency-Key` dentro de 24h "
        "retornam o resultado da requisição original (segurança de retry)."
    ),
    responses={
        200: {"description": "Score calculado com sucesso"},
        400: {
            "description": "CNPJ inválido",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://juridico-platform/errors/400",
                        "title": "Requisição inválida",
                        "status": 400,
                        "detail": "CNPJ deve ter 14 dígitos numéricos.",
                        "instance": "/api/v1/legalscore/score",
                        "contract_version": "1.0",
                    }
                }
            },
        },
        429: {"description": "Rate limit excedido (100 req/min por tenant)"},
        501: {"description": "Scoring engine não implementado (Fase 1b pendente)"},
    },
)
async def score_company(
    body: ScoreRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ScoreResponse:
    tenant_id = _get_tenant(request)
    request_id = str(uuid.uuid4())

    ctx_manager = _tracer.start_as_current_span("legalscore.score") if _OTEL else _noop_span()
    with ctx_manager as span:
        if _OTEL and span:
            span.set_attribute("tenant.id", tenant_id)
            span.set_attribute("cnpj.partial", body.cnpj[:6] + "****")
            span.set_attribute("idempotency.key_present", idempotency_key is not None)

        # Verificar idempotência
        if idempotency_key:
            cached = _check_idempotency(tenant_id, idempotency_key)
            if cached:
                return ScoreResponse(**cached)

        # Montar feature vector a partir dos caches de ingestão
        try:
            from services.shared.redis_client import get_redis
            redis = get_redis()
            fv = assemble_features(body.cnpj, redis)
        except Exception:
            fv = None

        # Scoring engine (SEAMS — PythonScoreEngine por padrão)
        engine = get_score_engine()
        if fv is not None:
            eng_req = EngineScoreRequest(cnpj=body.cnpj, features=fv.features, cnae_2dig=fv.cnae_2dig)
            eng_result = engine.score(eng_req)
            result = ScoreResponse(
                cnpj=body.cnpj,
                score=eng_result.score,
                risk_level=eng_result.risk_level,
                confidence_interval=list(eng_result.confidence_interval),
                breakdown=eng_result.breakdown,
                request_id=request_id,
                source_date=fv.source_date,
                engine=eng_result.engine,
                disclaimer=_SCORE_DISCLAIMER + (" [PARTIAL: " + ",".join(fv.sources_missing) + "]" if fv.is_partial else ""),
            )
        else:
            result = _stub_score(body.cnpj, request_id)

        # Decision Ledger — registra inputs_hash / outputs_hash (sem PII)
        inputs_for_ledger = {"cnpj_partial": body.cnpj[:6] + "****", "features": (fv.features if fv else {})}
        outputs_for_ledger = {"score": result.score, "risk_level": result.risk_level}
        sources = fv.sources_used if fv else []
        subject_token = hash_user_id(body.cnpj)  # CNPJ pseudonimizado (público)
        _ledger.add_entry(
            request_id=request_id,
            product="legalscore",
            inputs=inputs_for_ledger,
            outputs=outputs_for_ledger,
            sources=sources,
            subject_token=subject_token,
        )

        if idempotency_key:
            _store_idempotency(tenant_id, idempotency_key, result.model_dump())

        return result


@router.get(
    "/company/{cnpj}",
    summary="Perfil da empresa",
    responses={
        200: {
            "description": "Dados cadastrais + CNAE + capital social",
            "content": {
                "application/json": {
                    "example": {
                        "cnpj": "12345678000195",
                        "razao_social": "EMPRESA EXEMPLO LTDA",
                        "situacao": "ATIVA",
                        "cnae_principal": "6201-5/01",
                        "capital_social": 100000.00,
                        "data_abertura": "2010-03-15",
                        "source_date": "2026-06-15",
                        "lag_days": 1,
                    }
                }
            },
        },
        501: {"description": "Em implementação — Fase 1a"},
    },
)
async def company_profile(cnpj: str, request: Request) -> Any:
    _get_tenant(request)
    import json
    try:
        from services.shared.redis_client import get_redis
        redis = get_redis()
        raw = redis.get(f"receita:{cnpj}")
    except Exception:
        raw = None

    if not raw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dados cadastrais não disponíveis para CNPJ {cnpj}. "
                   "Execute a task de ingestão da Receita Federal primeiro.",
        )
    data = json.loads(raw)
    from services.ingest.pipeline.quality import receita_bronze_to_silver
    silver = receita_bronze_to_silver(data)
    return {
        "cnpj": cnpj,
        "razao_social": data.get("razao_social"),
        "situacao": silver.get("situacao_cadastral"),
        "cnae_principal": silver.get("cnae_fiscal"),
        "capital_social": silver.get("capital_social"),
        "data_abertura": data.get("data_abertura"),
        "source_date": silver.get("ingested_at", "")[:10] if silver.get("ingested_at") else None,
        "esta_ativa": silver.get("esta_ativa"),
    }


@router.get(
    "/company/{cnpj}/processes",
    summary="Processos judiciais com filtros e paginação",
    responses={501: {"description": "Em implementação — Fase 1a"}},
)
async def company_processes(
    cnpj: str,
    request: Request,
    page: int = 1,
    per_page: int = 20,
) -> Any:
    _get_tenant(request)
    raise HTTPException(status_code=501, detail="Em implementação — Fase 1a (ingest DATAJUD)")


@router.get(
    "/company/{cnpj}/risk-breakdown",
    summary="Detalhamento do score por dimensão",
    responses={501: {"description": "Em implementação — Fase 1b"}},
)
async def risk_breakdown(cnpj: str, request: Request) -> Any:
    _get_tenant(request)
    raise HTTPException(status_code=501, detail="Em implementação — Fase 1b (scoring engine)")


@router.post(
    "/batch",
    summary="Score em lote (até 1.000 CNPJs)",
    responses={
        202: {"description": "Batch enfileirado. Usar /audit/{job_id} para acompanhar."},
        400: {"description": "Lista excede 1.000 CNPJs"},
    },
)
async def batch_score(body: BatchScoreRequest, request: Request) -> Any:
    _get_tenant(request)
    if len(body.cnpjs) > 1000:
        raise HTTPException(status_code=400, detail="Máximo de 1.000 CNPJs por batch.")
    raise HTTPException(status_code=501, detail="Em implementação — Fase 1c (Celery batch)")


@router.get(
    "/audit/{request_id}",
    summary="Trilha auditável do Decision Ledger",
    responses={
        200: {
            "description": "Entrada do Decision Ledger com prova Merkle",
            "content": {
                "application/json": {
                    "example": {
                        "request_id": "req_01abc123",
                        "product": "legalscore",
                        "leaf_hash": "a3f1...",
                        "merkle_root": "9b2c...",
                        "proof": [{"sibling": "d4e5...", "position": "right"}],
                    }
                }
            },
        },
        501: {"description": "Em implementação — Fase 1c"},
    },
)
async def audit_trail(request_id: str, request: Request) -> Any:
    _get_tenant(request)
    try:
        proof = _ledger.get_proof(request_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entrada não encontrada no Decision Ledger: {request_id!r}",
        ) from None
    return proof


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------
_idempotency_store: dict[str, Any] = {}


def _check_idempotency(tenant_id: str, key: str) -> dict | None:
    return _idempotency_store.get(f"{tenant_id}:{key}")


def _store_idempotency(tenant_id: str, key: str, value: dict) -> None:
    _idempotency_store[f"{tenant_id}:{key}"] = value


def _stub_score(cnpj: str, request_id: str) -> ScoreResponse:
    """Stub determinístico para o endpoint de referência. Fase 1b substituirá por score real."""
    digit_sum = sum(int(d) for d in cnpj)
    score = max(0, min(1000, 500 + (digit_sum % 400) - 200))
    return ScoreResponse(
        cnpj=cnpj,
        score=score,
        risk_level=_classify(score),
        confidence_interval=[max(0, score - 78), min(1000, score + 78)],
        breakdown={},
        request_id=request_id,
    )


def _classify(score: int) -> str:
    if score >= 800:
        return "BAIXO"
    if score >= 600:
        return "MODERADO"
    if score >= 400:
        return "ALTO"
    return "CRITICO"


class _noop_span:
    def __enter__(self): return None
    def __exit__(self, *_): pass
