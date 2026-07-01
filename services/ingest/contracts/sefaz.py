"""
Data contract para alíquotas internas de ICMS extraídas de portais SEFAZ.

Fonte: portais estaduais (dado público). A alíquota interna efetiva do cálculo é
aliquota_pct + FCP; aqui guardamos os componentes separados com rastreabilidade.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

TRANSFORM_VERSION = "1.0.0"

_UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
    "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}


class SefazAliquotaBronze(BaseModel):
    """Schema de validação para uma alíquota interna raspada de uma SEFAZ."""

    uf: str
    produto: str = Field(..., min_length=1)
    ncm_prefix: str | None = None
    aliquota_pct: float = Field(..., ge=0, le=35)  # fora dessa faixa → quarentena
    fcp_pct: float | None = Field(None, ge=0, le=10)
    fundamento_legal: str | None = None

    # Linage
    source: str = "SEFAZ"
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    transform_version: str = TRANSFORM_VERSION

    @field_validator("uf")
    @classmethod
    def validate_uf(cls, v: str) -> str:
        v = str(v).strip().upper()
        if v not in _UFS:
            raise ValueError(f"UF inválida: {v!r}")
        return v

    @field_validator("ncm_prefix")
    @classmethod
    def validate_prefix(cls, v: str | None) -> str | None:
        if v is None:
            return None
        digitos = "".join(ch for ch in str(v) if ch.isdigit())
        return digitos or None
