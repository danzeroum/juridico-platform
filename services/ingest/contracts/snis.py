"""
Data contract para SNIS (Sistema Nacional de Informações sobre Saneamento Básico).

Bronze: indicadores brutos por município.
Silver: normalizado com percentuais calculados e linage.

Nota de frescor: dados SNIS têm lag médio de ~548 dias (publicação anual
com atraso). Todo payload carrega source_date e lag_days.
"""
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator

TRANSFORM_VERSION = "1.0.0"


class SnisMunicipioBronze(BaseModel):
    """Schema bruto de indicadores SNIS por município e exercício."""

    cod_ibge: str = Field(..., min_length=7, max_length=7)
    municipio: str = Field(..., min_length=1)
    uf: str = Field(..., min_length=2, max_length=2)
    exercicio: int = Field(..., ge=2000, le=2100)
    populacao_total: int = Field(..., ge=0)
    populacao_atendida_agua: int = Field(..., ge=0)
    populacao_atendida_esgoto: int = Field(..., ge=0)
    volume_agua_produzido: float | None = None
    volume_esgoto_coletado: float | None = None
    source_date: str | None = None  # YYYY-MM-DD da publicação

    # Linage
    source: str = "SNIS"
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


class SnisMunicipioSilver(BaseModel):
    """SNIS normalizado com percentuais e lag calculados."""

    cod_ibge: str
    municipio: str
    uf: str
    exercicio: int
    populacao_total: int
    cobertura_agua_pct: float   # 0–100
    cobertura_esgoto_pct: float  # 0–100
    source_date: str | None
    lag_days: int  # dias entre exercicio e ingestão

    # Linage
    source: str = "SNIS"
    ingested_at: str
    transform_version: str = TRANSFORM_VERSION


def snis_bronze_to_silver(bronze: SnisMunicipioBronze) -> SnisMunicipioSilver:
    """Transforma indicador SNIS de bronze para silver."""
    pop = bronze.populacao_total
    cob_agua = (bronze.populacao_atendida_agua / pop * 100) if pop > 0 else 0.0
    cob_esgoto = (bronze.populacao_atendida_esgoto / pop * 100) if pop > 0 else 0.0

    # Calcular lag a partir da data de publicação
    lag_days = -1
    if bronze.source_date:
        try:
            src = datetime.strptime(bronze.source_date, "%Y-%m-%d").replace(tzinfo=UTC)
            lag_days = (datetime.now(UTC) - src).days
        except ValueError:
            pass

    return SnisMunicipioSilver(
        cod_ibge=bronze.cod_ibge,
        municipio=bronze.municipio,
        uf=bronze.uf,
        exercicio=bronze.exercicio,
        populacao_total=bronze.populacao_total,
        cobertura_agua_pct=round(min(cob_agua, 100.0), 2),
        cobertura_esgoto_pct=round(min(cob_esgoto, 100.0), 2),
        source_date=bronze.source_date,
        lag_days=lag_days,
        ingested_at=bronze.ingested_at,
        transform_version=bronze.transform_version,
    )
