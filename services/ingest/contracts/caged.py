"""
Data contract para CAGED (Cadastro Geral de Empregados e Desempregados).

Bronze: schema de validação para o dado bruto do MTE.
Silver: normalizado com campos derivados e linage.
"""
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator

TRANSFORM_VERSION = "1.0.0"
SECOES_CNAE_VALIDAS = set("ABCDEFGHIJKLMNOPQRSTU")


class CagedEstabelecimentoBronze(BaseModel):
    """Schema de validação para registro bruto do CAGED por estabelecimento."""

    competencia: str = Field(..., description="YYYY-MM")
    cnpj_estabelecimento: str = Field(..., min_length=14, max_length=14)
    uf: str = Field(..., min_length=2, max_length=2)
    municipio: str = Field(..., min_length=1)
    secao_cnae: str = Field(..., min_length=1, max_length=1)
    saldo_admissoes_desligamentos: int
    admissoes: int | None = None
    desligamentos: int | None = None
    salario_medio: float | None = None
    grau_instrucao: str | None = None
    categoria: str | None = None

    # Linage
    source: str = "CAGED"
    ingested_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    transform_version: str = TRANSFORM_VERSION

    @field_validator("competencia")
    @classmethod
    def validate_competencia(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m")
        except ValueError as exc:
            raise ValueError(f"competencia deve ser YYYY-MM, recebido: {v!r}") from exc
        return v

    @field_validator("cnpj_estabelecimento")
    @classmethod
    def validate_cnpj(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("cnpj_estabelecimento deve conter apenas dígitos")
        return v

    @field_validator("uf")
    @classmethod
    def uppercase_uf(cls, v: str) -> str:
        return v.upper()

    @field_validator("secao_cnae")
    @classmethod
    def validate_secao_cnae(cls, v: str) -> str:
        u = v.upper()
        if u not in SECOES_CNAE_VALIDAS:
            raise ValueError(f"secao_cnae inválida: {v!r}")
        return u


class CagedEstabelecimentoSilver(BaseModel):
    """CAGED normalizado para feature extraction."""

    competencia: str
    cnpj_estabelecimento: str
    uf: str
    municipio: str
    secao_cnae: str
    saldo_admissoes_desligamentos: int
    admissoes: int
    desligamentos: int
    salario_medio_normalizado: float
    is_crescendo: bool

    # Linage
    source: str = "CAGED"
    ingested_at: str
    transform_version: str = TRANSFORM_VERSION
