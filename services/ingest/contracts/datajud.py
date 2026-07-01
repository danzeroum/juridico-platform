"""
Data contract para registros DATAJUD (Conselho Nacional de Justiça).

Bronze: validação de schema na ingestão + linage.
Silver: limpeza, normalização, pseudonimização aplicada.
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

TRANSFORM_VERSION = "1.0.0"


class DatajudProcessoBronze(BaseModel):
    """Schema de validação para registro bruto do DATAJUD."""

    # Campos do processo (obrigatórios)
    id_processo: str = Field(..., min_length=1)
    numero_processo: str = Field(..., min_length=1)
    data_julgamento: str = Field(..., description="YYYY-MM-DD")
    tribunal: str = Field(..., min_length=2)

    # Campos opcionais
    materia: str | None = None
    resultado: str | None = None
    valor_causa: float | None = None
    classe: str | None = None
    assunto: str | None = None  # código de assunto TPU (CNJ) — normalizado no silver

    # Partes (PII — pseudonimizado antes de storage)
    parte_cpf: str | None = None
    cpf_autor: str | None = None
    cpf_reu: str | None = None
    parte_nome: str | None = None
    nome_autor: str | None = None
    nome_reu: str | None = None

    # CNPJ mantido (dado público da Receita Federal)
    cnpj_parte: str | None = None

    # Linage (preenchido pelo pipeline)
    source: str = "DATAJUD"
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    transform_version: str = TRANSFORM_VERSION
    data_source_lag_days: int | None = None

    @field_validator("data_julgamento")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        date.fromisoformat(v)  # raises ValueError if invalid
        return v

    @field_validator("tribunal")
    @classmethod
    def validate_tribunal(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("cnpj_parte")
    @classmethod
    def validate_cnpj(cls, v: str | None) -> str | None:
        if v is None:
            return v
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) != 14:
            raise ValueError(f"CNPJ deve ter 14 dígitos, got {len(digits)}")
        return digits


class DatajudProcessoSilver(BaseModel):
    """Schema silver: pseudonimizado, enriquecido, pronto para feature engineering."""

    id_processo: str
    numero_processo: str
    data_julgamento: date
    tribunal: str
    materia: str | None = None
    resultado_normalizado: str | None = None  # PROVIMENTO/NEGADO/PARCIAL/OUTRO
    valor_causa: float | None = None
    valor_log: float = 0.0  # log1p(valor_causa) — feature para modelo
    cnpj_parte: str | None = None

    # Normalização TPU (Resolução CNJ 46) — chaves canônicas de agregação
    classe_tpu: str | None = None
    classe_label: str | None = None
    assunto_tpu: str | None = None
    assunto_label: str | None = None
    ramo: str | None = None  # TRABALHISTA | TRIBUTARIO | CONSUMIDOR | CIVEL | EMPRESARIAL | OUTRO

    # PII substituída por hashes HMAC
    parte_cpf_hash: str | None = None
    cpf_autor_hash: str | None = None
    cpf_reu_hash: str | None = None
    parte_nome_hash: str | None = None
    nome_autor_hash: str | None = None
    nome_reu_hash: str | None = None

    # Linage
    source: str = "DATAJUD"
    ingested_at: datetime
    transform_version: str = TRANSFORM_VERSION
    data_source_lag_days: int | None = None

    @field_validator("resultado_normalizado", mode="before")
    @classmethod
    def normalize_resultado(cls, v: Any) -> str | None:
        if v is None:
            return None
        v = str(v).upper()
        if any(k in v for k in ("PROVIM", "DADO PROVIM")):
            return "PROVIMENTO"
        if any(k in v for k in ("NEGAD", "IMPROVID")):
            return "NEGADO"
        if "PARCIAL" in v:
            return "PARCIAL"
        return "OUTRO"
