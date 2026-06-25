"""
Contratos da automação de protocolo (Defensor → órgãos de defesa do consumidor).

ProtocoloRequest  →  protocolar()  →  ProtocoloResultado

SEGURANÇA: protocolar em nome do consumidor é uma AÇÃO EXTERNA com efeito legal.
O modo padrão é SIMULAÇÃO (nenhuma submissão real). A submissão real só é tentada
com PROTOCOLO_MODO=real + credenciais do portal configuradas + host liberado na
allowlist de rede — ver docs/PROTOCOLO-AUTOMACAO.md.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from services.shared.contracts.defensor import Canal

PROTOCOLO_CONTRACT_VERSION = "protocolo/v1"


class ProtocoloModo(StrEnum):
    SIMULACAO = "simulacao"
    REAL = "real"


class ProtocoloStatus(StrEnum):
    SIMULADO = "SIMULADO"                       # modo simulação: nada foi submetido
    ENVIADO = "ENVIADO"                         # submissão real concluída
    FALHA = "FALHA"                             # tentativa real falhou
    AGUARDA_CREDENCIAIS = "AGUARDA_CREDENCIAIS" # modo real sem credenciais do portal
    CANAL_NAO_SUPORTADO = "CANAL_NAO_SUPORTADO" # sem driver real para o canal


class ProtocoloRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    canal:          Canal
    reclamante:     str = Field(..., min_length=3)
    reclamada:      str = Field(..., min_length=3)
    cnpj_reclamada: str | None = Field(None, pattern=r"^\d{14}$")
    resumo:         str = Field(..., min_length=20, max_length=5000)
    defesa:         str | None = Field(None, max_length=20000)
    valor:          float | None = Field(None, ge=0)
    anexos:         list[str] = Field(default_factory=list)


class ProtocoloResultado(BaseModel):
    model_config = ConfigDict(frozen=True)

    canal:            str
    modo:             str   # "simulacao" | "real"
    status:           str   # ProtocoloStatus
    numero_protocolo: str | None = None
    url:              str | None = None
    mensagem:         str
    enviado_em:       str
    contract_version: str = PROTOCOLO_CONTRACT_VERSION
