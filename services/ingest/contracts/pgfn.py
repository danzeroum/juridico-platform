"""
Data contract para registros PGFN (Procuradoria-Geral da Fazenda Nacional).

Fonte: Dívida Ativa da União — base legal: obrigação legal (LGPD art. 7º, II).
CNPJ é dado público; valores de dívida são indicadores de risco (não PII).
"""

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

TRANSFORM_VERSION = "1.0.0"


class PgfnDevedorBronze(BaseModel):
    """Schema de validação para registro bruto do PGFN."""

    cnpj: str = Field(..., description="14 dígitos sem formatação")
    situacao: str = Field(..., description="REGULAR|IRREGULAR|SUSPENSA|...")
    valor_total_divida: float | None = Field(None, ge=0)
    quantidade_debitos: int | None = Field(None, ge=0)
    data_inscricao: str | None = None  # YYYY-MM-DD da inscrição mais antiga
    tipo_devedor: str | None = None    # PJ|PF

    # Linage
    source: str = "PGFN"
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    transform_version: str = TRANSFORM_VERSION

    @field_validator("cnpj")
    @classmethod
    def validate_cnpj(cls, v: str) -> str:
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) != 14:
            raise ValueError(f"CNPJ deve ter 14 dígitos, got {len(digits)}")
        return digits

    @field_validator("situacao")
    @classmethod
    def normalize_situacao(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("data_inscricao")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        if v is not None:
            date.fromisoformat(v)
        return v


class PgfnDevedorSilver(BaseModel):
    """Schema silver: normalizado, pronto para features de risco."""

    cnpj: str
    situacao: str
    valor_total_divida: float = 0.0  # 0 se ausente (sem dívida conhecida)
    valor_divida_log: float = 0.0    # log1p(valor_total_divida) — feature
    quantidade_debitos: int = 0
    data_inscricao: date | None = None
    tipo_devedor: str = "PJ"
    tem_divida_ativa: bool = False

    # Linage
    source: str = "PGFN"
    ingested_at: datetime
    transform_version: str = TRANSFORM_VERSION
