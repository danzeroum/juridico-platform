"""
Settlement Optimizer — faixa ótima de acordo (ZOPA) por análise de decisão.

Estende a ConciliaIA com valores esperados explícitos + base rate jurimétrica.
Decisão auditável → Decision Ledger. Template P2.
"""
from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from services.settlement_optimizer.optimize import optimize_settlement

router = APIRouter(tags=["settlement-optimizer"])


def _get_tenant(request: Request) -> str:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token JWT não contém tenant_id.",
        )
    return tenant_id


class SettlementRequest(BaseModel):
    valor_causa: float = Field(..., ge=0)
    prob_favorable: float | None = Field(default=None, ge=0, le=1)
    pct_provimento: float | None = Field(default=None, ge=0, le=1)
    custo_autor: float = Field(default=0.0, ge=0)
    custo_reu: float = Field(default=0.0, ge=0)

    model_config = {"json_schema_extra": {"example": {
        "valor_causa": 100000, "prob_favorable": 0.6, "pct_provimento": 0.5,
        "custo_autor": 8000, "custo_reu": 12000,
    }}}


@router.post(
    "/optimize",
    summary="Faixa ótima de acordo (ZOPA) por análise de decisão",
    description=(
        "Calcula os valores esperados de continuar o litígio para autor e réu e a "
        "Zona de Possível Acordo. Heurística — registra no Decision Ledger."
    ),
    responses={200: {"description": "Faixa ótima e recomendação"}},
)
async def optimize(body: SettlementRequest, request: Request) -> Any:
    tenant_id = _get_tenant(request)
    request_id = str(uuid.uuid4())
    result = optimize_settlement(
        body.valor_causa, body.prob_favorable, body.pct_provimento,
        body.custo_autor, body.custo_reu,
    )
    try:
        _ledger_entry(tenant_id, request_id, body, result)
    except Exception:  # noqa: BLE001
        pass
    return {"request_id": request_id, **result}


def _ledger_entry(
    tenant_id: str, request_id: str, body: SettlementRequest, result: dict[str, Any]
) -> None:
    from services.shared.ledger.merkle import DecisionLedger

    if os.environ.get("DATABASE_URL"):
        from services.shared.ledger.merkle import PostgresDecisionLedger
        ledger: DecisionLedger = PostgresDecisionLedger(tenant_id)
    else:
        ledger = DecisionLedger()

    entry = ledger.add_entry(
        request_id=request_id,
        product="settlement-optimizer",
        inputs=body.model_dump(),
        outputs={"recomendacao": result.get("recomendacao"),
                 "acordo_sugerido": result.get("acordo_sugerido")},
        sources=["taxpredict", "jurimetria"],
        subject_token=None,
    )
    from services.shared.audit_log import log_ledger_write
    log_ledger_write(
        request_id=request_id, product="settlement-optimizer", tenant_id=tenant_id,
        entry_index=entry["entry_index"], has_subject_token=False,
    )
