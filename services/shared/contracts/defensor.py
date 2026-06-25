"""
Contratos da camada Defensor (agente jurídico de IA).

DefensorRequest  →  run_agente()  →  DefensorResponse

Defensor é a camada agêntica da plataforma: orquestra um pipeline multi-etapas
(classificar caso → consultar histórico → pedir subsídios → casar jurisprudência →
redigir defesa → preparar protocolo) e devolve uma timeline de eventos, além de
reaproveitar a montagem de peças do PetiBot e o RAG de jurisprudência.

Fase atual (scaffold): etapas determinísticas + RAG real. Sem loop de LLM e sem
integração real com portais (Procon/Consumidor.gov/Ouvidoria) — ver "Fora de escopo".
"""
from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from services.shared.contracts.petibot import PetiSection

DEFENSOR_CONTRACT_VERSION = "defensor/v1"


class Canal(StrEnum):
    """Foro / destino do protocolo da defesa."""
    PROCON         = "PROCON"
    CONSUMIDOR_GOV = "CONSUMIDOR_GOV"
    OUVIDORIA      = "OUVIDORIA"
    CONTENCIOSO    = "CONTENCIOSO"


class TipoCaso(StrEnum):
    """Tipo do caso — espelha TipoAcao do PetiBot (reaproveita a montagem de peça)."""
    TRABALHISTA    = "TRABALHISTA"
    CIVEL          = "CIVEL"
    TRIBUTARIO     = "TRIBUTARIO"
    PREVIDENCIARIO = "PREVIDENCIARIO"
    ADMINISTRATIVO = "ADMINISTRATIVO"
    CONSUMERISTA   = "CONSUMERISTA"


class DefensorRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    descricao:      str   = Field(..., min_length=50, max_length=5000)
    canal:          Canal
    tipo_caso:      TipoCaso
    reclamante:     str   = Field(..., min_length=3)
    reclamada:      str   = Field(..., min_length=3)
    cnpj_reclamada: str | None   = Field(None, pattern=r"^\d{14}$")
    valor:          float | None = Field(None, ge=0)


class EventoAgente(BaseModel):
    """Item da timeline do agente — modela o feed ao vivo (caso.classificado, ...)."""
    model_config = ConfigDict(frozen=True)

    ts:      str
    evento:  str
    detalhe: str
    status:  Literal["ok", "running", "pending"] = "ok"


class DefensorResponse(BaseModel):
    model_config = ConfigDict(frozen=True, protected_namespaces=())

    classificacao:           str
    canal:                   str
    eventos:                 list[EventoAgente]
    secoes:                  list[PetiSection]
    precedentes_encontrados: int  = Field(..., ge=0)
    casos_anteriores:        int  = Field(..., ge=0)
    subsidios:               list[str] = Field(default_factory=list)
    proximo_responsavel:     str  # "agente" | "humano" (handoff)
    status:                  str  # ex.: "DEFESA_PRONTA", "AGUARDA_PROTOCOLO"
    defesa_via:              str = "template"  # "llm" se redigida por LLM; senão "template"
    computed_at:             str
    contract_version:        str = DEFENSOR_CONTRACT_VERSION
