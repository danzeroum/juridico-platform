"""
Data contract para regras extraídas de convênios/protocolos do CONFAZ.

Regras extraídas por OCR/LLM NUNCA são persistidas direto: needs_review=True marca
para validação humana antes de virar alíquota vigente (plano §4).
"""
from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

TRANSFORM_VERSION = "1.0.0"

_NCM_RE = re.compile(r"^\d{8}$")


class ConfazRegraBronze(BaseModel):
    """Regra fiscal candidata extraída de um documento CONFAZ (pré-validação humana)."""

    ncm: str
    aliquota_pct: float | None = Field(None, ge=0, le=35)
    uf_origem: str | None = None
    uf_destino: str | None = None
    vigencia_inicio: str | None = None  # DD/MM/AAAA como capturado
    ato_ref: str | None = None
    needs_review: bool = True

    # Linage
    source: str = "CONFAZ"
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    transform_version: str = TRANSFORM_VERSION

    @field_validator("ncm")
    @classmethod
    def validate_ncm(cls, v: str) -> str:
        digitos = re.sub(r"\D", "", str(v))
        if not _NCM_RE.match(digitos):
            raise ValueError(f"NCM inválido: {v!r} (esperado 8 dígitos)")
        return digitos

    @field_validator("uf_origem", "uf_destino")
    @classmethod
    def upper_uf(cls, v: str | None) -> str | None:
        return v.strip().upper() if v else None
