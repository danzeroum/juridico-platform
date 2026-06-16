"""
Contrato da camada de scoring (FRONTEIRA Python <-> Rust).

Este modulo define a fronteira entre o servico de scoring e qualquer
implementacao concreta do motor de calculo. Todo chamador depende SOMENTE
destas abstracoes (ScoreRequest, ScoreResult, ScoreEngine) e nunca de uma
implementacao especifica.

Hoje a implementacao e Python puro. Amanha, quando um load test comprovar o
gargalo (gatilho: MLR > 2s para 1k CNPJs, conforme o plano), um crate Rust via
PyO3 implementa exatamente este mesmo Protocol e entra por troca de
configuracao, sem alterar nenhum chamador. A equivalencia comportamental entre
as duas implementacoes e garantida pela suite em
services/scoring/tests/contract/test_score_engine_contract.py.

Regra de ouro: a unica "lingua" falada na fronteira sao os modelos abaixo
(serializaveis, imutaveis). Nunca passe objetos Python especificos (sessoes de
banco, numpy arrays internos, etc.) atravessando esta linha.
"""
from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION = "scoring/v1"


class RiskLevel(str, Enum):
    BAIXO = "BAIXO"
    MODERADO = "MODERADO"
    ALTO = "ALTO"
    CRITICO = "CRITICO"


class ScoreRequest(BaseModel):
    """Entrada do calculo de score. Imutavel e serializavel."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cnpj: str = Field(..., pattern=r"^\d{14}$")
    cnae_2dig: str = Field(..., pattern=r"^\d{2}$")
    # features ja normalizadas/derivadas pelo data-enrichment (camada Python).
    # O motor recebe numeros prontos; ele nunca consulta banco nem rede.
    features: dict[str, float] = Field(default_factory=dict)


class ScoreResult(BaseModel):
    """Saida do calculo. O campo `engine` torna auditavel qual implementacao
    produziu o resultado — essencial durante a transicao Python -> Rust."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    score: int = Field(..., ge=0, le=1000)
    risk_level: RiskLevel
    confidence_interval: tuple[int, int]
    breakdown: dict[str, float] = Field(default_factory=dict)
    engine: str  # "python" | "rust" — gravado no Decision Ledger
    contract_version: str = CONTRACT_VERSION

    @model_validator(mode="after")
    def _check_ci(self) -> "ScoreResult":
        lo, hi = self.confidence_interval
        if lo > hi:
            raise ValueError("confidence_interval invalido: lower > upper")
        return self


class ScoringError(RuntimeError):
    """Erro de dominio do scoring."""


class ScoringUnavailable(ScoringError):
    """A implementacao escolhida nao esta disponivel/saudavel.

    Sinaliza ao factory que ele deve cair para o fallback (Python puro).
    """


@runtime_checkable
class ScoreEngine(Protocol):
    """A interface que TODA implementacao (Python, Rust, ...) deve satisfazer.

    Por ser um Protocol estrutural, a implementacao Rust nao precisa importar
    nada deste modulo — basta expor um objeto com `name`, `healthy()` e
    `score()`. Isso mantem o crate Rust sem dependencia do codigo Python.
    """

    name: str

    def healthy(self) -> bool:
        """Auto-teste barato. Para o adapter Rust, confirma que o modulo
        nativo carregou e responde a um input conhecido."""
        ...

    def score(self, request: ScoreRequest) -> ScoreResult:
        ...
