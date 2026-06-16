"""
Data contract para SICONFI (Sistema de Informações Contábeis e Fiscais do Setor Público).

Bronze: schema bruto da API STN.
Silver: normalizado com campos derivados e linage.
"""
from __future__ import annotations

import math
from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator

TRANSFORM_VERSION = "1.0.0"


class SiconfiContaBronze(BaseModel):
    """Schema bruto de uma entrada contábil SICONFI."""

    cod_ibge: str = Field(..., min_length=7, max_length=7)
    uf: str = Field(..., min_length=2, max_length=2)
    municipio: str = Field(..., min_length=1)
    exercicio: int = Field(..., ge=2000, le=2100)
    conta: str = Field(..., min_length=1)
    valor: float
    descricao_conta: str | None = None
    periodicidade: str | None = None
    periodo: str | None = None

    # Linage
    source: str = "SICONFI"
    ingested_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    transform_version: str = TRANSFORM_VERSION

    @field_validator("cod_ibge")
    @classmethod
    def validate_cod_ibge(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("cod_ibge deve conter apenas dígitos")
        return v

    @field_validator("uf")
    @classmethod
    def uppercase_uf(cls, v: str) -> str:
        return v.upper()

    @field_validator("conta")
    @classmethod
    def strip_conta(cls, v: str) -> str:
        return v.strip()


class SiconfiContaSilver(BaseModel):
    """SICONFI normalizado para cross-check."""

    cod_ibge: str
    uf: str
    municipio: str
    exercicio: int
    conta: str
    descricao_conta: str
    valor: float
    valor_log: float
    is_despesa: bool
    periodicidade: str
    periodo: str

    # Linage
    source: str = "SICONFI"
    ingested_at: str
    transform_version: str = TRANSFORM_VERSION


def siconfi_bronze_to_silver(bronze: SiconfiContaBronze) -> SiconfiContaSilver:
    """Transforma registro SICONFI de bronze para silver."""
    valor_abs = abs(bronze.valor)
    valor_log = math.log1p(valor_abs) if valor_abs >= 0 else 0.0
    is_despesa = bronze.conta.startswith(("3", "4"))

    return SiconfiContaSilver(
        cod_ibge=bronze.cod_ibge,
        uf=bronze.uf,
        municipio=bronze.municipio,
        exercicio=bronze.exercicio,
        conta=bronze.conta,
        descricao_conta=bronze.descricao_conta or "",
        valor=bronze.valor,
        valor_log=round(valor_log, 6),
        is_despesa=is_despesa,
        periodicidade=bronze.periodicidade or "ANUAL",
        periodo=bronze.periodo or "A",
        ingested_at=bronze.ingested_at,
        transform_version=bronze.transform_version,
    )
