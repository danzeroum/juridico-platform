"""
Implementacoes do ScoreEngine.

- PythonScoreEngine: a implementacao de hoje (MLR por CNAE em Python puro).
- RustScoreEngine: adapter fino sobre o crate PyO3 `rust_scorer`, que so existe
  quando o crate foi compilado via maturin. Enquanto o crate nao existe, o
  adapter se reporta como NAO saudavel e o factory cai para o Python.

Ambas as classes satisfazem o Protocol `ScoreEngine` definido em
services.shared.contracts.scoring.
"""
from __future__ import annotations

from services.shared.contracts.scoring import (
    RiskLevel,
    ScoreEngine,
    ScoreRequest,
    ScoreResult,
    ScoringUnavailable,
)

# Variaveis do modelo MLR, na ordem do contrato com a calibracao por CNAE.
FEATURE_NAMES: tuple[str, ...] = (
    "processos_ativos",
    "processos_trabalhistas",
    "divida_ativa_valor_log",
    "divida_ativa_crescimento",
    "saldo_emprego_12m",
    "capital_social_log",
    "processos_repetitivos",
)


def _classify(score: int) -> RiskLevel:
    if score >= 800:
        return RiskLevel.BAIXO
    if score >= 600:
        return RiskLevel.MODERADO
    if score >= 400:
        return RiskLevel.ALTO
    return RiskLevel.CRITICO


class PythonScoreEngine:
    """MLR por CNAE em Python puro. Deterministico para o mesmo input."""

    name = "python"

    def __init__(self, coefficient_loader=None) -> None:
        # coefficient_loader(cnae) -> dict com 'intercept' + um peso por feature
        # e, opcionalmente, 'sigma' (desvio do modelo) para o IC.
        self._load = coefficient_loader or self._default_coefficients

    @staticmethod
    def _default_coefficients(cnae_2dig: str) -> dict[str, float]:
        # Placeholder; em producao vem do PostgreSQL (calibracao por setor).
        coef = {name: 1.0 for name in FEATURE_NAMES}
        coef["intercept"] = 300.0
        coef["sigma"] = 40.0
        return coef

    def healthy(self) -> bool:
        return True

    def score(self, request: ScoreRequest) -> ScoreResult:
        coef = self._load(request.cnae_2dig)
        raw = coef.get("intercept", 0.0)
        breakdown: dict[str, float] = {}
        for name in FEATURE_NAMES:
            contribution = coef.get(name, 0.0) * request.features.get(name, 0.0)
            breakdown[name] = round(contribution, 4)
            raw += contribution

        score = max(0, min(1000, int(round(raw))))
        # IC derivado do desvio do modelo (sigma). NAO use bootstrap sobre
        # coeficientes fixos: isso so mede ruido das features, nao incerteza
        # real do modelo. O sigma deve vir da calibracao (covariancia dos betas).
        sigma = coef.get("sigma", 0.0)
        lo = max(0, int(round(score - 1.96 * sigma)))
        hi = min(1000, int(round(score + 1.96 * sigma)))

        return ScoreResult(
            score=score,
            risk_level=_classify(score),
            confidence_interval=(lo, hi),
            breakdown=breakdown,
            engine=self.name,
        )


class RustScoreEngine:
    """Adapter sobre o crate PyO3 `rust_scorer`.

    O crate expoe, por exemplo:
        rust_scorer.score(cnae: str, features: dict[str, float]) -> dict
    O adapter converte ScoreRequest -> primitivos, chama o modulo nativo e
    converte o retorno de volta para ScoreResult. Como `features` ja sao
    numeros, nada de Python especifico cruza a fronteira FFI.
    """

    name = "rust"

    def __init__(self) -> None:
        try:
            import rust_scorer  # type: ignore

            self._native = rust_scorer
        except ImportError:
            self._native = None

    def healthy(self) -> bool:
        if self._native is None:
            return False
        try:
            probe = self._native.score("00", {})  # input conhecido
            return isinstance(probe, dict) and "score" in probe
        except Exception:
            return False

    def score(self, request: ScoreRequest) -> ScoreResult:
        if self._native is None:
            raise ScoringUnavailable("crate rust_scorer nao compilado")
        try:
            out = self._native.score(request.cnae_2dig, dict(request.features))
        except Exception as exc:  # panic do Rust vira excecao Python aqui
            raise ScoringUnavailable(f"falha no modulo Rust: {exc}") from exc

        score = int(out["score"])
        lo, hi = out.get("confidence_interval", (score, score))
        return ScoreResult(
            score=score,
            risk_level=_classify(score),
            confidence_interval=(int(lo), int(hi)),
            breakdown=dict(out.get("breakdown", {})),
            engine=self.name,
        )
