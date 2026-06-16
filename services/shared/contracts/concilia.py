"""
Contratos da camada ConciliaIA (Fase 4).

ConciliaRequest  →  recommend_settlement()  →  ConciliaResponse

Combina prior histórico por tipo de ação, probabilidade TaxPredict e
risco do réu (LegalScore) para recomendar faixa de acordo.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from services.shared.contracts.petibot import TipoAcao

CONCILIA_CONTRACT_VERSION = "concilia/v1"


class ConciliaRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    descricao:   str   = Field(..., min_length=20, max_length=2000)
    valor_causa: float = Field(..., gt=0)
    tipo_acao:   TipoAcao
    cnpj_reu:    str | None = Field(None, pattern=r"^\d{14}$")
    cnpj_autor:  str | None = Field(None, pattern=r"^\d{14}$")


class ConciliaFator(BaseModel):
    model_config = ConfigDict(frozen=True)

    nome:     str
    impacto:  float = Field(..., ge=-1.0, le=1.0)
    descricao: str


class ConciliaResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    valor_minimo:             float = Field(..., ge=0)
    valor_sugerido:           float = Field(..., ge=0)
    valor_maximo:             float = Field(..., ge=0)
    percentual_causa:         float = Field(..., ge=0, le=1.0)
    fatores:                  list[ConciliaFator] = Field(default_factory=list)
    risco_reu:                int | None   = None
    probabilidade_procedencia: float | None = None
    computed_at:              str
    contract_version:         str = CONCILIA_CONTRACT_VERSION
