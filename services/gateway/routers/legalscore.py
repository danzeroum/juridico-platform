from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
# TODO: integrar com services/scoring na Fase 1

router = APIRouter()


class ScoreRequest(BaseModel):
    cnpj: str


class ScoreResponse(BaseModel):
    cnpj: str
    score: int
    risk_level: str
    confidence_interval: list[float]
    request_id: str


@router.post("/score/company", response_model=ScoreResponse)
async def score_company(request: ScoreRequest):
    """Score de risco juridico-financeiro de uma PJ por CNPJ."""
    # TODO: delegar para services/scoring na Fase 1
    raise HTTPException(status_code=501, detail="LegalScore em implementacao - Fase 1")


@router.get("/company/{cnpj}/profile")
async def company_profile(cnpj: str):
    """Dados cadastrais + CNAE + capital social."""
    raise HTTPException(status_code=501, detail="Em implementacao - Fase 1")


@router.get("/company/{cnpj}/processes")
async def company_processes(cnpj: str, page: int = 1, per_page: int = 20):
    """Processos judiciais com filtros."""
    raise HTTPException(status_code=501, detail="Em implementacao - Fase 1")


@router.get("/company/{cnpj}/risk-breakdown")
async def risk_breakdown(cnpj: str):
    """Detalhamento do score por dimensao."""
    raise HTTPException(status_code=501, detail="Em implementacao - Fase 1")


@router.post("/batch/score")
async def batch_score(cnpjs: list[str]):
    """Bulk scoring de ate 1000 CNPJs."""
    if len(cnpjs) > 1000:
        raise HTTPException(status_code=400, detail="Maximo de 1000 CNPJs por batch")
    raise HTTPException(status_code=501, detail="Em implementacao - Fase 1")


@router.get("/audit/{request_id}")
async def audit_trail(request_id: str):
    """Trilha completa do Decision Ledger para um request."""
    raise HTTPException(status_code=501, detail="Em implementacao - Fase 1")
