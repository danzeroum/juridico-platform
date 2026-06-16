"""
DanoBot — previsão de danos morais/materiais.

BLOQUEADO — aguarda parecer DPO (PD-06 em Pendencia.md).
DanoBot usa DATASUS (dado de saúde sensível, art. 11 LGPD).
Não pode ser implementado antes de:
  1. Opinião formal do DPO
  2. Análise de risco de re-identificação
  3. Possível RIPD (Relatório de Impacto à Proteção de Dados)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("/danobot/predict")
async def predict() -> None:
    """Previsão de danos morais/materiais — bloqueado até PD-06."""
    raise HTTPException(
        status_code=501,
        detail={
            "type": "https://juridico.io/errors/danobot/blocked-pd06",
            "title": "DanoBot bloqueado",
            "status": 501,
            "detail": (
                "DanoBot requer DATASUS (dado de saúde sensível, LGPD art. 11). "
                "Implementação bloqueada até parecer do DPO (PD-06). "
                "Consulte Pendencia.md para acompanhar o desbloqueio."
            ),
            "instance": "/api/v1/danobot/predict",
            "contract_version": "danobot/v1",
        },
    )
