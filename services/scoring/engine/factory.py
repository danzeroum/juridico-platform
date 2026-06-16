"""
Selecao do motor de scoring + fallback automatico.

A troca Python -> Rust e uma mudanca de CONFIGURACAO, nao de codigo:

    SCORING_BACKEND=python   # default hoje
    SCORING_BACKEND=rust     # exige Rust; falha se indisponivel
    SCORING_BACKEND=auto     # usa Rust se saudavel, senao Python

`with_fallback` envolve o motor primario de modo que, se uma chamada lancar
ScoringUnavailable (ex.: erro recuperavel no modulo nativo), ela cai para o
Python na hora, em runtime — sem derrubar a request.

NOTA DE SEGURANCA: fallback cobre ERRO/indisponibilidade. Um segfault real do
Rust derruba o processo Python inteiro; isso exige a outra camada de defesa
do plano (supervisor que reinicia o worker + health check antes de aceitar
trafego). Fallback e health check sao complementares, nao substitutos.
"""
from __future__ import annotations

from services.scoring.engine.engines import PythonScoreEngine, RustScoreEngine
from services.shared.contracts.scoring import (
    ScoreEngine,
    ScoreRequest,
    ScoreResult,
    ScoringUnavailable,
)


class _FallbackEngine:
    """Tenta o primario; em ScoringUnavailable, usa o secundario."""

    def __init__(self, primary: ScoreEngine, secondary: ScoreEngine) -> None:
        self._primary = primary
        self._secondary = secondary
        self.name = f"{primary.name}->{secondary.name}"

    def healthy(self) -> bool:
        return self._primary.healthy() or self._secondary.healthy()

    def score(self, request: ScoreRequest) -> ScoreResult:
        try:
            return self._primary.score(request)
        except ScoringUnavailable:
            return self._secondary.score(request)


def get_score_engine(backend: str = "auto") -> ScoreEngine:
    backend = (backend or "auto").lower()
    python = PythonScoreEngine()

    if backend == "python":
        return python

    rust = RustScoreEngine()
    if backend == "rust":
        if not rust.healthy():
            raise ScoringUnavailable("SCORING_BACKEND=rust mas o crate nao esta saudavel")
        return _FallbackEngine(rust, python)  # ainda protege erros em runtime

    # auto
    if rust.healthy():
        return _FallbackEngine(rust, python)
    return python
