"""
ContabilIA — upload de DRE e relatório de auditoria contábil.

Endpoints:
  POST /api/v1/contabilia/audit/upload  — envia DRE (CSV), retorna relatório JSON
  GET  /api/v1/contabilia/audit/{report_id} — recupera relatório por ID

Formato DRE aceito (CSV):
  Cabeçalho obrigatório: conta,valor
  Cabeçalho opcional: conta,valor,descricao

Campos financeiros reconhecidos (case-insensitive):
  receita_liquida, headcount, ativo_circulante, passivo_circulante,
  ebitda, importacoes, variacao_estoque, receita_servicos_publicos

Série temporal: linhas com conta = "receita_mensal_YYYY_MM" ou
  "despesa_mensal_YYYY_MM" são agregadas em serie_receitas_mensais /
  serie_despesas_mensais para Benford/Z-score.

SLA: p95 < 60s (processamento em memória, sem I/O externo).
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from services.audit.crosscheck.engine import CrossCheckEngine, CrossCheckFinding

router = APIRouter()

_engine = CrossCheckEngine()

ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "text/plain",
    "application/csv",
    "application/vnd.ms-excel",
}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

FINANCIAL_FIELDS = {
    "receita_liquida", "headcount", "ativo_circulante", "passivo_circulante",
    "ebitda", "importacoes", "variacao_estoque", "receita_servicos_publicos",
}


def _parse_dre_csv(content: bytes) -> dict:
    """
    Parseia DRE no formato CSV (conta,valor[,descricao]).

    Retorna dicionário com campos financeiros e séries temporais.
    Linhas inválidas (valor não-numérico) são ignoradas silenciosamente.
    """
    text = content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    financials: dict = {}
    serie_receitas: list[float] = []
    serie_despesas: list[float] = []

    for row in reader:
        conta = (row.get("conta") or "").strip().lower()
        valor_raw = (row.get("valor") or "").strip().replace(",", ".")

        try:
            valor = float(valor_raw)
        except ValueError:
            continue

        # Séries temporais (Benford e Z-score)
        if conta.startswith("receita_mensal"):
            serie_receitas.append(valor)
            continue
        if conta.startswith("despesa_mensal"):
            serie_despesas.append(valor)
            continue

        # Campos financeiros pontuais
        if conta in FINANCIAL_FIELDS:
            financials[conta] = valor

    if serie_receitas:
        financials["serie_receitas_mensais"] = serie_receitas
    if serie_despesas:
        financials["serie_despesas_mensais"] = serie_despesas

    return financials


def _findings_to_dict(findings: list[CrossCheckFinding]) -> list[dict]:
    return [
        {"rule": f.rule, "severity": f.severity, "description": f.description, "detail": f.detail}
        for f in findings
    ]


def _severity_summary(findings: list[CrossCheckFinding]) -> dict[str, int]:
    summary: dict[str, int] = {"CRITICO": 0, "ALTO": 0, "MEDIO": 0}
    for f in findings:
        summary[f.severity] = summary.get(f.severity, 0) + 1
    return summary


@router.post("/audit/upload")
async def upload_financials(
    file: UploadFile = File(...),  # noqa: B008
    cnpj: str | None = None,
) -> JSONResponse:
    """
    Upload de DRE em CSV e retorno de relatório de auditoria.

    Aceita: text/csv, text/plain, application/csv
    Tamanho máximo: 5 MB
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://juridico.io/errors/formato-nao-suportado",
                "title": "Formato não suportado",
                "status": 400,
                "detail": f"Content-Type '{file.content_type}' não aceito. Use text/csv.",
                "instance": "/api/v1/contabilia/audit/upload",
                "contract_version": "contabilia/v1",
            },
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail={
                "type": "https://juridico.io/errors/arquivo-muito-grande",
                "title": "Arquivo muito grande",
                "status": 413,
                "detail": f"Tamanho máximo: {MAX_FILE_SIZE // 1024 // 1024} MB",
                "instance": "/api/v1/contabilia/audit/upload",
                "contract_version": "contabilia/v1",
            },
        )

    financials = _parse_dre_csv(content)
    if not financials:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "https://juridico.io/errors/dre-invalida",
                "title": "DRE inválida",
                "status": 422,
                "detail": "Nenhum campo financeiro reconhecido no CSV. Verifique o formato.",
                "instance": "/api/v1/contabilia/audit/upload",
                "contract_version": "contabilia/v1",
            },
        )

    # Dados públicos (sem fonte real em Fase 2 — marcado como ausente)
    public_data: dict = {}

    findings = _engine.run_checks(financials, public_data)
    report_id = str(uuid.uuid4())
    generated_at = datetime.now(UTC).isoformat()

    report = {
        "report_id": report_id,
        "generated_at": generated_at,
        "cnpj": cnpj,
        "filename": file.filename,
        "status": "CONCLUIDO",
        "summary": _severity_summary(findings),
        "total_findings": len(findings),
        "findings": _findings_to_dict(findings),
        "fields_analyzed": list(financials.keys()),
        "data_lag_note": "Dados públicos (CAGED/SICONFI) não consultados nesta versão — cross-checks CC01/CC02 requerem ingest prévio.",
        "contract_version": "contabilia/v1",
    }

    return JSONResponse(content=report, status_code=200)


@router.get("/audit/{report_id}")
async def get_report(report_id: str) -> JSONResponse:
    """
    Recupera relatório de auditoria por ID.

    Nota: relatórios são gerados de forma síncrona e retornados
    diretamente no POST. Este endpoint é reservado para relatórios
    assíncronos (Fase 3).
    """
    raise HTTPException(
        status_code=404,
        detail={
            "type": "https://juridico.io/errors/relatorio-nao-encontrado",
            "title": "Relatório não encontrado",
            "status": 404,
            "detail": f"Relatório '{report_id}' não encontrado. Relatórios síncronos são retornados diretamente no POST.",
            "instance": f"/api/v1/contabilia/audit/{report_id}",
            "contract_version": "contabilia/v1",
        },
    )
