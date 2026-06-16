"""
Contrato da camada TaxPredict (Fase 3b).

TaxPredictRequest  →  predict()  →  TaxPredictResponse

O modelo Bayesiano (services/taxpredict/model/bayesian.py) nunca roda MCMC
no path da request. O trace é pré-carregado no startup; predict() condiciona
via pm.set_data(). Recalibração agendada em Celery Beat.

RAG: ChromaDB + BGE-M3 (Ollama) para busca semântica de jurisprudências.
"""
from __future__ import annotations

import math
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

TAXPREDICT_CONTRACT_VERSION = "taxpredict/v1"

# Prior nacional (fallback quando trace não carregado)
PRIOR_NACIONAL: float = 0.30
PRIOR_CI_LOWER: float = 0.10
PRIOR_CI_UPPER: float = 0.55

_ANO_REF: int = 2024

# Peso por matéria para feature indicador_economico (0.0–1.0)
_MATERIA_INDICADOR: dict[str, float] = {
    "PIS_COFINS": 0.80,
    "IRPJ":       0.70,
    "CSLL":       0.60,
    "ICMS":       0.50,
    "IPI":        0.40,
    "ISS":        0.30,
    "SIMPLES":    0.20,
}


class Materia(StrEnum):
    PIS_COFINS = "PIS_COFINS"
    IRPJ       = "IRPJ"
    CSLL       = "CSLL"
    ICMS       = "ICMS"
    IPI        = "IPI"
    ISS        = "ISS"
    SIMPLES    = "SIMPLES"


class Decisao(StrEnum):
    FAVORAVEL    = "FAVORAVEL"
    DESFAVORAVEL = "DESFAVORAVEL"
    PARCIAL      = "PARCIAL"
    DESCONHECIDO = "DESCONHECIDO"


class TaxPredictRequest(BaseModel):
    """Entrada da API TaxPredict."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    descricao: str      = Field(..., min_length=20, max_length=2000)
    materia:   Materia
    valor:     float | None = Field(None, ge=0.0)
    orgao_autuante: str | None = None
    ano_autuacao:   int | None = Field(None, ge=2000, le=2100)


class JurisprudenciaHit(BaseModel):
    """Jurisprudência retornada pelo RAG."""

    model_config = ConfigDict(frozen=True)

    doc_id:     str
    similarity: float = Field(..., ge=0.0, le=1.0)
    ementa:     str
    decisao:    Decisao = Decisao.DESCONHECIDO
    tribunal:   str | None = None
    ano:        int | None = None


class TaxPredictResponse(BaseModel):
    """Resposta da API TaxPredict com probabilidade e contexto jurisprudencial."""

    model_config = ConfigDict(frozen=True, protected_namespaces=())

    materia:          str
    probability:      float = Field(..., ge=0.0, le=1.0)
    ci_lower:         float = Field(..., ge=0.0, le=1.0)
    ci_upper:         float = Field(..., ge=0.0, le=1.0)
    rag_hits:         int   = Field(..., ge=0)
    jurisprudencias:  list[JurisprudenciaHit] = Field(default_factory=list)
    features_used:    dict[str, float]        = Field(default_factory=dict)
    computed_at:      str
    model_version:    str
    is_fallback:      bool = False
    contract_version: str  = TAXPREDICT_CONTRACT_VERSION


def extract_features(request: TaxPredictRequest) -> dict[str, float]:
    """
    Extrai features do modelo Bayesiano a partir da requisição.
    Puro Python, sem I/O. Determinístico dado o mesmo input.

    Features:
      valor_log           — log10(valor + 1) / 10; escala 0..~0.6 para valores até 1B
      recencia            — 1.0 = autuação em _ANO_REF; diminui 0.1/ano; piso 0.0
      indicador_economico — proxy de complexidade fiscal por matéria (0.20–0.80)
    """
    valor_log = math.log10(request.valor + 1) / 10.0 if request.valor else 0.0
    anos_atras = _ANO_REF - (request.ano_autuacao or _ANO_REF)
    recencia = max(0.0, min(1.0, 1.0 - anos_atras * 0.1))
    indicador_economico = _MATERIA_INDICADOR.get(str(request.materia), 0.50)
    return {
        "valor_log":           round(valor_log, 4),
        "recencia":            round(recencia, 4),
        "indicador_economico": indicador_economico,
    }
