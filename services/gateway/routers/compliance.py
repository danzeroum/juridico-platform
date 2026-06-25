"""
ComplianceRadar — API de monitoramento municipal.

Endpoints:
  GET /api/v1/compliance/municipalities           — lista municípios com indicadores
  GET /api/v1/compliance/municipality/{ibge_code} — indicadores detalhados
  GET /api/v1/compliance/alerts                   — alertas ativos (paginado)
  POST /api/v1/compliance/municipality/{ibge_code}/evaluate — avalia regras agora

SLA: dashboard < 30s (dados do Redis cache).
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from services.compliance.monitor import build_indicadores_from_cache, evaluate_municipio
from services.compliance.rules import ALERT_RULES

router = APIRouter()

# OTel — graceful degradation
try:
    from opentelemetry import trace as otel_trace
    _tracer = otel_trace.get_tracer("compliance")
    _OTEL = True
except ImportError:
    _OTEL = False
    _tracer = None  # type: ignore[assignment]

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def _get_redis():
    import redis as redis_lib

    return redis_lib.from_url(_REDIS_URL, decode_responses=True)


def _cached(r, key: str) -> dict | None:
    val = r.get(key)
    if val is None:
        return None
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return None


def _ibge_error(ibge_code: str, instance: str) -> dict:
    return {
        "type": "https://juridico.io/errors/ibge-invalido",
        "title": "Código IBGE inválido",
        "status": 400,
        "detail": "cod_ibge deve conter exatamente 7 dígitos numéricos.",
        "instance": instance,
        "contract_version": "compliance/v1",
    }


def _cache_error(instance: str) -> dict:
    return {
        "type": "https://juridico.io/errors/cache-indisponivel",
        "title": "Cache indisponível",
        "status": 503,
        "detail": "Redis inacessível — dados de compliance indisponíveis.",
        "instance": instance,
        "contract_version": "compliance/v1",
    }


def _build_summary(cod_ibge: str, r) -> dict:
    now = datetime.now(UTC)
    ref = now.strftime("%Y-%m")
    last_ref = f"{now.year - 1:04d}-{now.month:02d}"

    siconfi = _cached(r, f"siconfi:{cod_ibge}:{now.year}")
    siconfi_ant = _cached(r, f"siconfi:{cod_ibge}:{now.year - 1}")
    caged = _cached(r, f"caged:{cod_ibge}:{ref}")
    caged_ant = _cached(r, f"caged:{cod_ibge}:{last_ref}")
    snis_data = _cached(r, f"snis:{cod_ibge}")
    snis = snis_data[0] if isinstance(snis_data, list) and snis_data else snis_data

    ind = build_indicadores_from_cache(
        cod_ibge=cod_ibge,
        referencia=ref,
        siconfi_atual=siconfi,
        siconfi_anterior=siconfi_ant,
        caged_atual=caged,
        caged_anterior=caged_ant,
        snis=snis,
    )
    alerts = evaluate_municipio(ind)

    ibge = _cached(r, f"ibge:{cod_ibge}") or {}

    return {
        "cod_ibge": cod_ibge,
        "municipio": ibge.get("municipio"),
        "uf": ibge.get("uf"),
        "populacao": ibge.get("populacao"),
        "referencia": ref,
        "indicadores": {
            "delta_arrecadacao_yoy": ind.delta_arrecadacao_yoy,
            "delta_emprego_yoy": ind.delta_emprego_yoy,
            "cobertura_agua_pct": ind.cobertura_agua_pct,
            "cobertura_esgoto_pct": ind.cobertura_esgoto_pct,
            "source_lag_days": ind.source_lag_days,
            "source_date": ind.source_date,
        },
        "sources_missing": ind.sources_missing or [],
        "active_alerts": len(alerts),
        "alert_rules_triggered": [a.rule_id for a in alerts],
    }


@router.get(
    "/municipalities",
    summary="Lista municípios monitorados",
    responses={
        200: {
            "description": "Lista paginada de municípios com indicadores",
            "content": {
                "application/json": {
                    "example": {
                        "total": 1, "page": 1, "per_page": 20,
                        "municipalities": [{
                            "cod_ibge": "3550308", "referencia": "2026-06",
                            "indicadores": {
                                "delta_arrecadacao_yoy": -0.25,
                                "delta_emprego_yoy": -0.12,
                                "cobertura_agua_pct": 42.0,
                                "cobertura_esgoto_pct": 21.0,
                                "source_lag_days": 548,
                                "source_date": "2024-10-01",
                            },
                            "sources_missing": [],
                            "active_alerts": 2,
                            "alert_rules_triggered": ["arrecadacao_critica", "saneamento_baixo"],
                        }],
                        "contract_version": "compliance/v1",
                    }
                }
            },
        },
        503: {
            "description": "Redis indisponível",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://juridico.io/errors/cache-indisponivel",
                        "title": "Cache indisponível",
                        "status": 503,
                        "detail": "Redis inacessível — dados de compliance indisponíveis.",
                        "instance": "/api/v1/compliance/municipalities",
                        "contract_version": "compliance/v1",
                    }
                }
            },
        },
    },
)
async def list_municipalities(
    uf: str | None = Query(None, description="Filtrar por UF (ex: SP)"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> JSONResponse:
    """Lista municípios monitorados com indicadores de compliance."""
    try:
        r = _get_redis()
        # Universo de municípios monitorados: SNIS (saneamento) ∪ IBGE (seed real).
        codes: set[str] = {k.split(":")[1] for k in r.keys("snis:*") if ":" in k}
        codes |= {k.split(":")[1] for k in r.keys("ibge:*") if ":" in k}
        ibge_codes = sorted(codes)

        if uf:
            uf_upper = uf.upper()
            filtered = []
            for code in ibge_codes:
                data = _cached(r, f"snis:{code}")
                entry = data[0] if isinstance(data, list) and data else data
                code_uf = (entry or {}).get("uf") or (_cached(r, f"ibge:{code}") or {}).get("uf")
                if code_uf == uf_upper:
                    filtered.append(code)
            ibge_codes = filtered

        total = len(ibge_codes)
        start = (page - 1) * per_page
        page_codes = ibge_codes[start : start + per_page]

        municipalities = []
        for code in page_codes:
            try:
                municipalities.append(_build_summary(code, r))
            except Exception:
                municipalities.append({"cod_ibge": code, "error": "dados indisponíveis"})

        return JSONResponse(content={
            "total": total,
            "page": page,
            "per_page": per_page,
            "municipalities": municipalities,
            "contract_version": "compliance/v1",
        })
    except Exception as exc:
        raise HTTPException(status_code=503, detail=_cache_error("/api/v1/compliance/municipalities")) from exc


@router.get(
    "/municipality/{ibge_code}",
    summary="Indicadores detalhados de um município",
    responses={
        200: {
            "description": "Indicadores e alertas do município",
            "content": {
                "application/json": {
                    "example": {
                        "cod_ibge": "3550308", "referencia": "2026-06",
                        "indicadores": {
                            "delta_arrecadacao_yoy": -0.25,
                            "delta_emprego_yoy": -0.12,
                            "cobertura_agua_pct": 42.0,
                            "cobertura_esgoto_pct": 21.0,
                            "source_lag_days": 548,
                            "source_date": "2024-10-01",
                        },
                        "sources_missing": [],
                        "active_alerts": 2,
                        "alert_rules_triggered": ["arrecadacao_critica", "saneamento_baixo"],
                        "rules_available": ["arrecadacao_critica", "saneamento_baixo"],
                        "lgpd_note": "DATASUS excluído desta versão — aguarda parecer DPO (PD-06).",
                        "contract_version": "compliance/v1",
                    }
                }
            },
        },
        400: {
            "description": "Código IBGE inválido",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://juridico.io/errors/ibge-invalido",
                        "title": "Código IBGE inválido",
                        "status": 400,
                        "detail": "cod_ibge deve conter exatamente 7 dígitos numéricos.",
                        "instance": "/api/v1/compliance/municipality/INVALIDO",
                        "contract_version": "compliance/v1",
                    }
                }
            },
        },
    },
)
async def municipality_detail(ibge_code: str) -> JSONResponse:
    """Indicadores detalhados e alertas de um município."""
    if not ibge_code.isdigit() or len(ibge_code) != 7:
        raise HTTPException(
            status_code=400,
            detail=_ibge_error(ibge_code, f"/api/v1/compliance/municipality/{ibge_code}"),
        )
    ctx_manager = _tracer.start_as_current_span("compliance.municipality_detail") if _OTEL else _noop_span()
    with ctx_manager as span:
        if _OTEL and span:
            span.set_attribute("ibge_code", ibge_code)
        try:
            r = _get_redis()
            summary = _build_summary(ibge_code, r)
            summary["rules_available"] = [rule["id"] for rule in ALERT_RULES]
            summary["lgpd_note"] = "DATASUS excluído desta versão — aguarda parecer DPO (PD-06)."
            return JSONResponse(content=summary)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=_cache_error(f"/api/v1/compliance/municipality/{ibge_code}"),
            ) from exc


@router.get("/alerts")
async def list_alerts(
    severity: str | None = Query(None, description="Filtrar: LOW|MEDIUM|HIGH|CRITICAL"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> JSONResponse:
    """Alertas gerados pelo ComplianceRadar (lidos do cache Redis)."""
    try:
        r = _get_redis()
        keys = r.keys("compliance_alert:*")
        alerts_raw = []
        for key in keys:
            data = _cached(r, key)
            if data:
                alerts_raw.append(data)

        if severity:
            sev_upper = severity.upper()
            alerts_raw = [a for a in alerts_raw if a.get("severity") == sev_upper]

        total = len(alerts_raw)
        start = (page - 1) * per_page
        page_alerts = alerts_raw[start : start + per_page]

        return JSONResponse(content={
            "total": total,
            "page": page,
            "per_page": per_page,
            "alerts": page_alerts,
            "contract_version": "compliance/v1",
        })
    except Exception as exc:
        raise HTTPException(status_code=503, detail=_cache_error("/api/v1/compliance/alerts")) from exc


@router.post("/municipality/{ibge_code}/evaluate")
async def evaluate_municipality(ibge_code: str) -> JSONResponse:
    """
    Avalia regras de compliance para um município agora.

    Retorna os AlertEnvelopes gerados sem publicá-los (preview/debug).
    """
    if not ibge_code.isdigit() or len(ibge_code) != 7:
        raise HTTPException(
            status_code=400,
            detail=_ibge_error(ibge_code, f"/api/v1/compliance/municipality/{ibge_code}/evaluate"),
        )
    try:
        r = _get_redis()
        now = datetime.now(UTC)
        ref = now.strftime("%Y-%m")
        last_ref = f"{now.year - 1:04d}-{now.month:02d}"

        siconfi = _cached(r, f"siconfi:{ibge_code}:{now.year}")
        siconfi_ant = _cached(r, f"siconfi:{ibge_code}:{now.year - 1}")
        caged = _cached(r, f"caged:{ibge_code}:{ref}")
        caged_ant = _cached(r, f"caged:{ibge_code}:{last_ref}")
        snis_data = _cached(r, f"snis:{ibge_code}")
        snis = snis_data[0] if isinstance(snis_data, list) and snis_data else snis_data

        ind = build_indicadores_from_cache(
            cod_ibge=ibge_code,
            referencia=ref,
            siconfi_atual=siconfi,
            siconfi_anterior=siconfi_ant,
            caged_atual=caged,
            caged_anterior=caged_ant,
            snis=snis,
        )
        envelopes = evaluate_municipio(ind)

        return JSONResponse(content={
            "cod_ibge": ibge_code,
            "evaluated_at": now.isoformat(),
            "rules_fired": len(envelopes),
            "envelopes": [json.loads(e.model_dump_json()) for e in envelopes],
            "contract_version": "compliance/v1",
        })
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "type": "https://juridico.io/errors/avaliacao-falhou",
                "title": "Avaliação falhou",
                "status": 503,
                "detail": str(exc),
                "instance": f"/api/v1/compliance/municipality/{ibge_code}/evaluate",
                "contract_version": "compliance/v1",
            },
        ) from exc


@router.get(
    "/uf/{uf}/municipios",
    summary="Lista municípios de uma UF ao vivo do IBGE",
    responses={
        200: {
            "description": "Municípios da UF coletados direto do IBGE (servicodados.ibge.gov.br)",
            "content": {
                "application/json": {
                    "example": {
                        "uf": "DF", "total": 1,
                        "municipios": [{"cod_ibge": "5300108", "municipio": "Brasília", "uf": "DF"}],
                        "source": "IBGE", "contract_version": "compliance/v1",
                    }
                }
            },
        },
    },
)
async def list_uf_municipios(uf: str) -> JSONResponse:
    """Lista municípios de uma UF coletados ao vivo do IBGE (degradação graciosa: lista vazia)."""
    if not uf.isalpha() or len(uf) != 2:
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://juridico.io/errors/uf-invalida",
                "title": "UF inválida",
                "status": 400,
                "detail": "uf deve conter exatamente 2 letras (ex.: SP).",
                "instance": f"/api/v1/compliance/uf/{uf}/municipios",
                "contract_version": "compliance/v1",
            },
        )
    from services.ingest.tasks.ibge import fetch_municipios

    municipios = fetch_municipios(uf)
    return JSONResponse(content={
        "uf": uf.upper(),
        "total": len(municipios),
        "municipios": municipios,
        "source": "IBGE",
        "contract_version": "compliance/v1",
    })


@router.get(
    "/municipio/{cod_ibge}/populacao",
    summary="População residente estimada (IBGE) de um município",
)
async def municipio_populacao(cod_ibge: str) -> JSONResponse:
    """População residente estimada do município, coletada ao vivo do IBGE (SIDRA 6579)."""
    if not cod_ibge.isdigit() or len(cod_ibge) != 7:
        raise HTTPException(
            status_code=400,
            detail=_ibge_error(cod_ibge, f"/api/v1/compliance/municipio/{cod_ibge}/populacao"),
        )
    from services.ingest.tasks.ibge import fetch_populacao

    populacao, ano = fetch_populacao(cod_ibge)
    return JSONResponse(content={
        "cod_ibge": cod_ibge,
        "populacao": populacao,
        "ano": ano,
        "source": "IBGE",
        "contract_version": "compliance/v1",
    })


@router.get(
    "/municipio/{cod_ibge}/perfil",
    summary="Perfil socioeconômico (IBGE) de um município",
)
async def municipio_perfil(cod_ibge: str) -> JSONResponse:
    """
    Perfil socioeconômico do município coletado ao vivo do IBGE:
    população estimada, PIB a preços correntes e PIB per capita derivado.
    """
    if not cod_ibge.isdigit() or len(cod_ibge) != 7:
        raise HTTPException(
            status_code=400,
            detail=_ibge_error(cod_ibge, f"/api/v1/compliance/municipio/{cod_ibge}/perfil"),
        )
    from services.ingest.tasks.ibge import (
        fetch_area,
        fetch_cempre,
        fetch_pib,
        fetch_populacao,
    )

    populacao, pop_ano = fetch_populacao(cod_ibge)
    pib_mil, pib_ano = fetch_pib(cod_ibge)
    pib_reais = pib_mil * 1000 if pib_mil is not None else None
    pib_per_capita = (
        round(pib_reais / populacao, 2) if pib_reais and populacao else None
    )
    cempre = fetch_cempre(cod_ibge)
    area_km2, area_ano = fetch_area(cod_ibge)
    densidade = (
        round(populacao / area_km2, 2) if populacao and area_km2 else None
    )
    return JSONResponse(content={
        "cod_ibge": cod_ibge,
        "populacao": populacao,
        "populacao_ano": pop_ano,
        "pib_reais": pib_reais,
        "pib_ano": pib_ano,
        "pib_per_capita": pib_per_capita,
        "empresas": cempre.get("empresas"),
        "pessoal_ocupado": cempre.get("pessoal_ocupado"),
        "pessoal_assalariado": cempre.get("pessoal_assalariado"),
        "cempre_ano": cempre.get("ano"),
        "area_km2": area_km2,
        "area_ano": area_ano,
        "densidade_demografica": densidade,
        "source": "IBGE",
        "contract_version": "compliance/v1",
    })


class _noop_span:
    def __enter__(self): return None
    def __exit__(self, *_): pass
