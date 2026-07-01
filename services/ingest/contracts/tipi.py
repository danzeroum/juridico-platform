"""
Data contract para a TIPI (Tabela de Incidência do IPI) — Receita Federal.

Fonte: CSV oficial da RFB (dado público, LGPD art. 7º, IV). Sem PII.
O campo EX (exceção) é tratado à parte — maior foco de erro em sistemas fiscais.
"""
from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

TRANSFORM_VERSION = "1.0.0"

_NCM_RE = re.compile(r"^\d{8}$")


class TipiBronze(BaseModel):
    """Schema de validação para uma linha bruta da TIPI."""

    ncm_codigo: str = Field(..., description="8 dígitos sem formatação")
    descricao: str = Field(..., min_length=1)
    aliquota_ipi: float | None = Field(None, ge=0, le=400)
    excecao: str | None = None
    capitulo: str | None = None

    # Linage
    source: str = "TIPI"
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    transform_version: str = TRANSFORM_VERSION

    @field_validator("ncm_codigo")
    @classmethod
    def validate_ncm(cls, v: str) -> str:
        digitos = "".join(ch for ch in str(v) if ch.isdigit())
        if not _NCM_RE.match(digitos):
            raise ValueError(f"NCM inválido: {v!r} (esperado 8 dígitos)")
        return digitos

    @model_validator(mode="after")
    def derive_capitulo(self) -> TipiBronze:
        if not self.capitulo and self.ncm_codigo:
            self.capitulo = self.ncm_codigo[:2]
        return self
