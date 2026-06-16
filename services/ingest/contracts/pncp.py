"""
Data contract para PNCP (Portal Nacional de Contratações Públicas).

Bronze: contrato bruto por órgão/fornecedor.
Silver: enriquecido com prazo de abertura, flags dispensa/único-proponente e valor_log.
"""
from __future__ import annotations

import math
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

TRANSFORM_VERSION = "1.0.0"


class Modalidade(StrEnum):
    PREGAO_ELETRONICO  = "PREGAO_ELETRONICO"
    PREGAO_PRESENCIAL  = "PREGAO_PRESENCIAL"
    CONCORRENCIA       = "CONCORRENCIA"
    TOMADA_PRECOS      = "TOMADA_PRECOS"
    CONVITE            = "CONVITE"
    DISPENSA           = "DISPENSA"
    INEXIGIBILIDADE    = "INEXIGIBILIDADE"
    LEILAO             = "LEILAO"
    OUTRA              = "OUTRA"

_MODALIDADES_DISPENSA = {Modalidade.DISPENSA, Modalidade.INEXIGIBILIDADE}


class PncpContratoBronze(BaseModel):
    """Schema bruto de contrato PNCP por órgão e exercício."""

    numero_controle: str = Field(..., min_length=1)
    cnpj_orgao:      str = Field(..., pattern=r"^\d{14}$")
    cnpj_fornecedor: str | None = None
    objeto:          str = Field(..., min_length=1)
    modalidade:      Modalidade
    valor_contrato:  float = Field(..., ge=0)
    data_publicacao: str              # YYYY-MM-DD
    data_abertura:   str | None = None  # YYYY-MM-DD
    num_propostas:   int | None = Field(None, ge=0)

    source:            str = "PNCP"
    ingested_at:       str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    transform_version: str = TRANSFORM_VERSION

    @field_validator("cnpj_fornecedor")
    @classmethod
    def validate_cnpj_fornecedor(cls, v: str | None) -> str | None:
        if v is not None and not v.isdigit():
            raise ValueError("cnpj_fornecedor deve conter apenas dígitos")
        return v


class PncpContratoSilver(BaseModel):
    """PNCP enriquecido com métricas de integridade competitiva."""

    numero_controle:     str
    cnpj_orgao:          str
    cnpj_fornecedor:     str | None
    objeto:              str
    modalidade:          str
    valor_contrato:      float
    valor_log:           float    # log10(valor_contrato + 1)
    data_publicacao:     str
    prazo_abertura_dias: int | None  # dias entre publicação e abertura
    is_dispensa:         bool
    is_unico_proponente: bool

    source:            str
    ingested_at:       str
    transform_version: str = TRANSFORM_VERSION


def pncp_bronze_to_silver(bronze: PncpContratoBronze) -> PncpContratoSilver:
    """Transforma contrato PNCP de bronze para silver."""
    valor_log = math.log10(bronze.valor_contrato + 1)

    prazo_dias: int | None = None
    if bronze.data_publicacao and bronze.data_abertura:
        try:
            from datetime import datetime as dt
            pub = dt.strptime(bronze.data_publicacao, "%Y-%m-%d")
            abe = dt.strptime(bronze.data_abertura, "%Y-%m-%d")
            prazo_dias = (abe - pub).days
        except ValueError:
            pass

    is_dispensa = bronze.modalidade in _MODALIDADES_DISPENSA
    is_unico = bronze.num_propostas == 1

    return PncpContratoSilver(
        numero_controle=bronze.numero_controle,
        cnpj_orgao=bronze.cnpj_orgao,
        cnpj_fornecedor=bronze.cnpj_fornecedor,
        objeto=bronze.objeto,
        modalidade=bronze.modalidade.value,
        valor_contrato=bronze.valor_contrato,
        valor_log=round(valor_log, 4),
        data_publicacao=bronze.data_publicacao,
        prazo_abertura_dias=prazo_dias,
        is_dispensa=is_dispensa,
        is_unico_proponente=is_unico,
        source=bronze.source,
        ingested_at=bronze.ingested_at,
    )
