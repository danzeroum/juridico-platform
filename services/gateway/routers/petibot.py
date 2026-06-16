"""
PetiBot — montagem de petição jurídica.

Endpoints:
  POST /api/v1/petibot/assemble
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.petibot.assembler import assemble_petition
from services.shared.contracts.petibot import PetiRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/petibot/assemble")
async def assemble(case: PetiRequest) -> JSONResponse:
    """
    Monta estrutura de petição com seções padrão e precedentes via RAG.

    Fase 4: retorna template (sem geração LLM).
    Precedentes via ChromaDB; degradação graciosa se offline.
    """
    response = assemble_petition(case)
    return JSONResponse(content=response.model_dump(), status_code=200)
