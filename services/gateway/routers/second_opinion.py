"""
Second Opinion Engine — parecer estatístico de consenso entre produtos.

Combina sinais (LegalScore, TaxPredict, jurimetria) num veredito de favorabilidade.
Produz decisão auditável → registra no Decision Ledger. Template P2.
"""
from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from services.second_opinion.consensus import synthesize_opinion

router = APIRouter(tags=["second-opinion"])


def _get_tenant(request: Request) -> str:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token JWT não contém tenant_id.",
        )
    return tenant_id


class SecondOpinionRequest(BaseModel):
    legalscore: float | None = Field(default=None, ge=0, le=1000)
    taxpredict_prob: float | None = Field(default=None, ge=0, le=1)
    pct_provimento: float | None = Field(default=None, ge=0, le=1)

    model_config = {"json_schema_extra": {"example": {
        "legalscore": 720, "taxpredict_prob": 0.68, "pct_provimento": 0.55,
    }}}


@router.post(
    "/opinion",
    summary="Segunda opinião estatística sobre um caso",
    description=(
        "Combina sinais de LegalScore, TaxPredict e jurimetria num veredito de "
        "favorabilidade com nível de concordância. Heurística — registra entrada "
        "no Decision Ledger."
    ),
    responses={200: {"description": "Parecer sintetizado (ou status=sem_sinais)"}},
)
async def opinion(body: SecondOpinionRequest, request: Request) -> Any:
    tenant_id = _get_tenant(request)
    request_id = str(uuid.uuid4())
    result = synthesize_opinion(body.legalscore, body.taxpredict_prob, body.pct_provimento)

    try:
        _ledger_entry(tenant_id, request_id, body, result)
    except Exception:  # noqa: BLE001 — ledger indisponível não derruba o parecer
        pass

    return {"request_id": request_id, **result}


def _ledger_entry(
    tenant_id: str, request_id: str, body: SecondOpinionRequest, result: dict[str, Any]
) -> None:
    from services.shared.ledger.merkle import DecisionLedger

    if os.environ.get("DATABASE_URL"):
        from services.shared.ledger.merkle import PostgresDecisionLedger
        ledger: DecisionLedger = PostgresDecisionLedger(tenant_id)
    else:
        ledger = DecisionLedger()

    entry = ledger.add_entry(
        request_id=request_id,
        product="second-opinion",
        inputs=body.model_dump(),
        outputs={"veredito": result.get("veredito"), "favorabilidade": result.get("favorabilidade")},
        sources=["legalscore", "taxpredict", "jurimetria"],
        subject_token=None,  # parecer sobre sinais agregados — sem titular direto
    )
    from services.shared.audit_log import log_ledger_write
    log_ledger_write(
        request_id=request_id, product="second-opinion", tenant_id=tenant_id,
        entry_index=entry["entry_index"], has_subject_token=False,
    )
