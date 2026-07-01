"""
Data contract para indicadores da ABJ (Associação Brasileira de Jurimetria).

Bronze: linha crua de um dataset abjData / observatório (CSV).
Silver: normalizado, com taxa de congestionamento derivada e linage.

Base legal (ROPA): dado público tornado disponível pela ABJ (datasets abertos).
LICENÇA: confirmar termos de redistribuição de cada dataset abjData antes de uso
comercial. Por padrão a ingestão ABJ é DESLIGADA (settings.ABJ_ENABLED=false) e
serve como fonte de validação/semente de TPU — ver services/ingest/tasks/abj.py.
"""
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator

TRANSFORM_VERSION = "1.0.0"


class AbjIndicadorBronze(BaseModel):
    """Linha bruta de indicador jurimétrico da ABJ."""

    tribunal: str = Field(..., min_length=2)
    periodo: str = Field(..., min_length=4)  # 'YYYY' | 'YYYY-Qn' | 'YYYY-MM'
    classe_cnj: str | None = None
    assunto_cnj: str | None = None
    tempo_medio_dias: float | None = None
    taxa_congestionamento: float | None = None
    casos_novos: int | None = None
    casos_baixados: int | None = None
    casos_pendentes: int | None = None

    # Linage
    source: str = "ABJ"
    ingested_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    transform_version: str = TRANSFORM_VERSION

    @field_validator("tribunal")
    @classmethod
    def upper_tribunal(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("taxa_congestionamento")
    @classmethod
    def validate_taxa(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if not 0.0 <= v <= 1.0:
            raise ValueError("taxa_congestionamento deve estar em [0, 1]")
        return v


class AbjIndicadorSilver(BaseModel):
    """Indicador ABJ normalizado, pronto para landing em jurimetria.abj_indicador_raw."""

    tribunal: str
    periodo: str
    classe_cnj: str | None = None
    assunto_cnj: str | None = None
    tempo_medio_dias: float | None = None
    taxa_congestionamento: float | None = None
    casos_novos: int | None = None
    casos_baixados: int | None = None
    casos_pendentes: int | None = None

    source: str = "ABJ"
    ingested_at: str
    transform_version: str = TRANSFORM_VERSION


def abj_bronze_to_silver(bronze: AbjIndicadorBronze) -> AbjIndicadorSilver:
    """
    Bronze → Silver. Deriva `taxa_congestionamento` da fórmula Justiça em Números
    (pendentes / (baixados + pendentes)) quando ausente e os contadores existem.
    """
    taxa = bronze.taxa_congestionamento
    if taxa is None and bronze.casos_pendentes is not None and bronze.casos_baixados is not None:
        denom = bronze.casos_baixados + bronze.casos_pendentes
        taxa = round(bronze.casos_pendentes / denom, 4) if denom > 0 else None

    return AbjIndicadorSilver(
        tribunal=bronze.tribunal,
        periodo=bronze.periodo,
        classe_cnj=bronze.classe_cnj,
        assunto_cnj=bronze.assunto_cnj,
        tempo_medio_dias=bronze.tempo_medio_dias,
        taxa_congestionamento=taxa,
        casos_novos=bronze.casos_novos,
        casos_baixados=bronze.casos_baixados,
        casos_pendentes=bronze.casos_pendentes,
        ingested_at=bronze.ingested_at,
        transform_version=bronze.transform_version,
    )
