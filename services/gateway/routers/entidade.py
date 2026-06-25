"""
Entidade — hub de cadastro de PJ (Receita Federal / CNPJ público).

Endpoints:
  GET /api/v1/entidade/{cnpj}  — cadastro público do CNPJ
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()

ENTIDADE_CONTRACT_VERSION = "entidade/v1"


@router.get(
    "/{cnpj}",
    summary="Cadastro público de um CNPJ (Receita Federal)",
    responses={
        200: {
            "description": "Cadastro do CNPJ; campos vazios se a fonte estiver indisponível",
            "content": {
                "application/json": {
                    "example": {
                        "cnpj": "00000000000191",
                        "encontrado": True,
                        "cadastro": {
                            "razao_social": "Empresa Exemplo S.A.",
                            "situacao_cadastral": "ATIVA",
                            "porte": "DEMAIS",
                            "cnae_fiscal": "6201501",
                            "municipio": "São Paulo",
                            "uf": "SP",
                        },
                        "source": "Receita/CNPJ",
                        "contract_version": "entidade/v1",
                    }
                }
            },
        },
        422: {"description": "CNPJ inválido (deve ter 14 dígitos)"},
    },
)
async def get_entidade(cnpj: str) -> JSONResponse:
    """Cadastro público do CNPJ, coletado ao vivo da Receita (degradação graciosa)."""
    digits = "".join(c for c in cnpj if c.isdigit())
    if len(digits) != 14:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "https://juridico.io/errors/cnpj-invalido",
                "title": "CNPJ inválido",
                "status": 422,
                "detail": "cnpj deve conter 14 dígitos.",
                "instance": f"/api/v1/entidade/{cnpj}",
                "contract_version": ENTIDADE_CONTRACT_VERSION,
            },
        )
    from services.ingest.tasks.receita_cnpj import fetch_cnpj

    cadastro = fetch_cnpj(digits)
    return JSONResponse(content={
        "cnpj": digits,
        "encontrado": bool(cadastro),
        "cadastro": cadastro,
        "source": "Receita/CNPJ",
        "contract_version": ENTIDADE_CONTRACT_VERSION,
    })
