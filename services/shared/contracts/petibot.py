"""
Contratos da camada PetiBot (Fase 4).

PetiRequest  →  assemble_petition()  →  PetiResponse

Sem LLM na Fase 4: seções retornam templates que o advogado preenche.
RAG (ChromaDB + BGE-M3) fornece precedentes; degradação graciosa se offline.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

PETIBOT_CONTRACT_VERSION = "petibot/v1"

SECOES_MINIMAS_POR_TIPO: dict[str, list[str]] = {
    "TRABALHISTA":    ["DOS FATOS", "DO DIREITO", "DAS VERBAS RESCISÓRIAS", "DOS PEDIDOS"],
    "CIVEL":          ["DOS FATOS", "DO DIREITO", "DOS DANOS", "DOS PEDIDOS"],
    "TRIBUTARIO":     ["DOS FATOS", "DO DIREITO TRIBUTÁRIO", "DA ILEGALIDADE", "DOS PEDIDOS"],
    "PREVIDENCIARIO": ["DOS FATOS", "DO DIREITO PREVIDENCIÁRIO", "DO BENEFÍCIO", "DOS PEDIDOS"],
    "ADMINISTRATIVO": ["DOS FATOS", "DO DIREITO ADMINISTRATIVO", "DO CABIMENTO", "DOS PEDIDOS"],
    "CONSUMERISTA":   ["DOS FATOS", "DO DIREITO DO CONSUMIDOR", "DOS DANOS", "DOS PEDIDOS"],
}


class TipoAcao(StrEnum):
    TRABALHISTA    = "TRABALHISTA"
    CIVEL          = "CIVEL"
    TRIBUTARIO     = "TRIBUTARIO"
    PREVIDENCIARIO = "PREVIDENCIARIO"
    ADMINISTRATIVO = "ADMINISTRATIVO"
    CONSUMERISTA   = "CONSUMERISTA"


class PetiRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    descricao:    str   = Field(..., min_length=50, max_length=5000)
    tipo_acao:    TipoAcao
    polo_ativo:   str   = Field(..., min_length=3)
    polo_passivo: str   = Field(..., min_length=3)
    valor_causa:  float | None = Field(None, ge=0)
    cnpj_parte:   str | None   = Field(None, pattern=r"^\d{14}$")


class PetiSection(BaseModel):
    model_config = ConfigDict(frozen=True)

    titulo:      str
    conteudo:    str
    precedentes: list[str] = Field(default_factory=list)


class PetiResponse(BaseModel):
    model_config = ConfigDict(frozen=True, protected_namespaces=())

    tipo_acao:              str
    polo_ativo:             str
    polo_passivo:           str
    secoes:                 list[PetiSection]
    precedentes_encontrados: int  = Field(..., ge=0)
    risk_score:             int | None   = None
    probability_favorable:  float | None = None
    computed_at:            str
    contract_version:       str = PETIBOT_CONTRACT_VERSION
