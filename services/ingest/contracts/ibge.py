"""
Data contract para IBGE (indicadores municipais — SIDRA/IBGE Cidades).

Bronze: indicadores socioeconômicos brutos por município.
Silver: normalizado com linage.
"""
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator

TRANSFORM_VERSION = "1.0.0"


class IbgeMunicipioBronze(BaseModel):
    """Schema bruto de indicadores IBGE por município."""

    cod_ibge: str = Field(..., min_length=7, max_length=7)
    municipio: str = Field(..., min_length=1)
    uf: str = Field(..., min_length=2, max_length=2)
    ano: int = Field(..., ge=2000, le=2100)
    populacao: int = Field(..., ge=0)
    pib_per_capita: float | None = None
    idhm: float | None = Field(None, ge=0.0, le=1.0)
    taxa_desemprego: float | None = Field(None, ge=0.0, le=100.0)
    area_km2: float | None = Field(None, ge=0.0)
    source_date: str | None = None

    # Linage
    source: str = "IBGE"
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


class IbgeMunicipioSilver(BaseModel):
    """IBGE normalizado com densidade populacional calculada."""

    cod_ibge: str
    municipio: str
    uf: str
    ano: int
    populacao: int
    pib_per_capita: float
    idhm: float
    taxa_desemprego: float
    densidade_demografica: float  # hab/km²
    source_date: str | None
    lag_days: int

    # Linage
    source: str = "IBGE"
    ingested_at: str
    transform_version: str = TRANSFORM_VERSION


def ibge_bronze_to_silver(bronze: IbgeMunicipioBronze) -> IbgeMunicipioSilver:
    """Transforma indicador IBGE de bronze para silver com defaults seguros."""
    lag_days = -1
    if bronze.source_date:
        try:
            src = datetime.strptime(bronze.source_date, "%Y-%m-%d").replace(tzinfo=UTC)
            lag_days = (datetime.now(UTC) - src).days
        except ValueError:
            pass

    densidade = 0.0
    if bronze.area_km2 and bronze.area_km2 > 0:
        densidade = round(bronze.populacao / bronze.area_km2, 2)

    return IbgeMunicipioSilver(
        cod_ibge=bronze.cod_ibge,
        municipio=bronze.municipio,
        uf=bronze.uf,
        ano=bronze.ano,
        populacao=bronze.populacao,
        pib_per_capita=bronze.pib_per_capita or 0.0,
        idhm=bronze.idhm or 0.0,
        taxa_desemprego=bronze.taxa_desemprego or 0.0,
        densidade_demografica=densidade,
        source_date=bronze.source_date,
        lag_days=lag_days,
        ingested_at=bronze.ingested_at,
        transform_version=bronze.transform_version,
    )
