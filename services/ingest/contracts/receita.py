"""
Data contract para registros da Receita Federal (CNPJ público).

Fonte: API pública de CNPJ — dado tornado público (LGPD art. 7º, IV).
Nenhum campo é PII individual; CNPJ de PJ é dado público.
"""

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

TRANSFORM_VERSION = "1.0.0"

SITUACOES_VALIDAS = {"ATIVA", "BAIXADA", "INAPTA", "SUSPENSA", "NULA"}


class ReceitaCnpjBronze(BaseModel):
    """Schema de validação para registro bruto da Receita Federal."""

    cnpj: str = Field(..., description="14 dígitos sem formatação")
    razao_social: str = Field(..., min_length=1)
    situacao_cadastral: str
    data_situacao_cadastral: str | None = None  # YYYY-MM-DD
    porte: str | None = None   # ME|EPP|DEMAIS|GRANDE
    natureza_juridica: str | None = None
    capital_social: float | None = Field(None, ge=0)
    data_abertura: str | None = None  # YYYY-MM-DD
    municipio: str | None = None
    uf: str | None = None
    cnaes_secundarios: list[str] | None = None
    cnae_fiscal: str | None = None

    # Linage
    source: str = "RECEITA"
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    transform_version: str = TRANSFORM_VERSION

    @field_validator("cnpj")
    @classmethod
    def validate_cnpj(cls, v: str) -> str:
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) != 14:
            raise ValueError(f"CNPJ deve ter 14 dígitos, got {len(digits)}")
        return digits

    @field_validator("situacao_cadastral")
    @classmethod
    def normalize_situacao(cls, v: str) -> str:
        normalized = v.upper().strip()
        if normalized not in SITUACOES_VALIDAS:
            raise ValueError(f"Situação inválida: {v!r}. Válidas: {SITUACOES_VALIDAS}")
        return normalized

    @field_validator("data_abertura", "data_situacao_cadastral")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        if v is not None:
            date.fromisoformat(v)
        return v

    @field_validator("uf")
    @classmethod
    def normalize_uf(cls, v: str | None) -> str | None:
        return v.upper().strip() if v else None


class ReceitaCnpjSilver(BaseModel):
    """Schema silver: normalizado, pronto para features de risco."""

    cnpj: str
    razao_social: str
    situacao_cadastral: str
    data_situacao_cadastral: date | None = None
    porte: str = "DESCONHECIDO"
    natureza_juridica: str | None = None
    capital_social: float = 0.0
    capital_social_log: float = 0.0  # log1p(capital_social) — feature
    data_abertura: date | None = None
    idade_empresa_anos: float | None = None  # feature derivada
    municipio: str | None = None
    uf: str | None = None
    cnae_fiscal: str | None = None
    esta_ativa: bool = False

    # Linage
    source: str = "RECEITA"
    ingested_at: datetime
    transform_version: str = TRANSFORM_VERSION
