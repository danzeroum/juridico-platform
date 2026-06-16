"""
Modelo Bayesiano Hierárquico para TaxPredict (Fase 3b).

BUGS CORRIGIDOS:
- predict() agora aceita `case: dict` e condiciona no caso via pm.set_data()
  (antes retornava constante 0.65 ignorando o input).
- MCMC (pm.sample) NUNCA roda no path da request. Roda apenas em fit(), que é
  chamado por tarefa Celery Beat (agendada). A preditiva posterior é pré-calculada
  e o trace é carregado UMA VEZ no startup do processo.
- API PyMC5: pm.MutableData para features condicionáveis.

STARTUP:
    model = TaxPredictionModel("PIS/COFINS")
    model.load_from_minio(minio_client, bucket="gold", key="taxpredict/pis_cofins.nc")

REQUEST PATH:
    result = model.predict({"valor_log": 5.2, "recencia": 0.3, "indicador_economico": 0.1})

TREINAMENTO (Celery Beat — nunca on-demand):
    model.fit(df_treino)
    model.save_to_minio(minio_client, bucket="gold", key="taxpredict/pis_cofins.nc")
"""
from __future__ import annotations

import logging
from io import BytesIO
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class TaxPredictionModel:
    """
    Modelo hierárquico bayesiano para previsão de desfecho tributário.
    Níveis: prior nacional → nível matéria → caso individual.
    """

    def __init__(self, materia: str) -> None:
        self.materia = materia
        self._model: Any = None
        self._trace: Any = None
        self._is_loaded = False

    # ------------------------------------------------------------------
    # Treinamento — executar SOMENTE via Celery Beat, nunca por request
    # ------------------------------------------------------------------
    def fit(self, data: "pd.DataFrame") -> None:  # type: ignore[name-defined]
        """
        Treina o modelo com MCMC. Salvar o trace com save_to_minio() após o fit.
        NÃO chamar em request path — latência inaceitável (minutos).
        """
        try:
            import pymc as pm
            import pandas as pd  # noqa: F401
        except ImportError as exc:
            raise ImportError("pymc e pandas são necessários para fit()") from exc

        with pm.Model() as model:
            # MutableData permite substituir valores sem recompilar o grafo
            valor_log = pm.MutableData("valor_log", data["valor_log"].values, dims="obs")
            recencia = pm.MutableData("recencia", data["recencia"].values, dims="obs")
            indicador = pm.MutableData("indicador_economico", data["indicador_economico"].values, dims="obs")

            # Prior nacional
            mu_national = pm.Normal("mu_national", mu=0.3, sigma=0.15)
            # Efeitos das features
            beta_valor = pm.Normal("beta_valor", mu=0, sigma=0.1)
            beta_recencia = pm.Normal("beta_recencia", mu=0, sigma=0.1)
            beta_economico = pm.Normal("beta_economico", mu=0, sigma=0.05)

            logit_p = (
                mu_national
                + beta_valor * valor_log
                + beta_recencia * recencia
                + beta_economico * indicador
            )
            p = pm.Deterministic("p", pm.math.sigmoid(logit_p), dims="obs")
            pm.Bernoulli("obs", p=p, observed=data["sucesso"].values, dims="obs")

            self._trace = pm.sample(
                draws=500,
                tune=500,
                chains=2,
                target_accept=0.9,
                random_seed=42,
                progressbar=False,
            )
        self._model = model
        self._is_loaded = True
        logger.info("TaxPredictionModel.fit() concluído para matéria=%s", self.materia)

    # ------------------------------------------------------------------
    # Persistência do trace (MinIO)
    # ------------------------------------------------------------------
    def save_to_minio(self, minio_client: Any, bucket: str, key: str) -> None:
        """Serializa trace para NetCDF e persiste no MinIO."""
        try:
            import arviz as az
        except ImportError as exc:
            raise ImportError("arviz é necessário para serialização do trace") from exc
        if not self._is_loaded:
            raise RuntimeError("Nenhum trace disponível. Chame fit() primeiro.")
        buf = BytesIO()
        az.to_netcdf(self._trace, buf)
        buf.seek(0)
        minio_client.put_object(bucket, key, buf, buf.getbuffer().nbytes)
        logger.info("Trace salvo em minio://%s/%s", bucket, key)

    def load_from_minio(self, minio_client: Any, bucket: str, key: str) -> None:
        """
        Carrega trace do MinIO. Deve ser chamado UMA VEZ no startup do processo.
        Se MinIO estiver offline, o serviço NÃO sobe (health check falha) —
        em vez de tentar recarregar por request.
        """
        try:
            import arviz as az
            import pymc as pm
        except ImportError as exc:
            raise ImportError("arviz e pymc são necessários para load_from_minio()") from exc
        data = minio_client.get_object(bucket, key).read()
        self._trace = az.from_netcdf(BytesIO(data))
        self._is_loaded = True
        logger.info("Trace carregado de minio://%s/%s", bucket, key)

    # ------------------------------------------------------------------
    # Predição — path da request; MCMC nunca roda aqui
    # ------------------------------------------------------------------
    def predict(self, case: dict[str, float]) -> dict[str, float]:
        """
        Amostra a preditiva posterior condicionada no caso de entrada.
        Requer trace carregado (load_from_minio no startup).
        Sem MCMC: usa draws do trace existente.
        """
        if not self._is_loaded or self._trace is None:
            raise RuntimeError(
                "Trace não carregado. Chame load_from_minio() no startup do serviço."
            )
        if self._model is None:
            raise RuntimeError(
                "Modelo não disponível. O serviço deve ser reiniciado com trace válido."
            )

        try:
            import pymc as pm
        except ImportError as exc:
            raise ImportError("pymc é necessário para predict()") from exc

        with self._model:
            pm.set_data({
                "valor_log": np.array([case.get("valor_log", 0.0)]),
                "recencia": np.array([case.get("recencia", 0.0)]),
                "indicador_economico": np.array([case.get("indicador_economico", 0.0)]),
            })
            ppc = pm.sample_posterior_predictive(
                self._trace,
                var_names=["p"],
                random_seed=42,
                progressbar=False,
            )

        draws = ppc.posterior_predictive["p"].values.flatten()
        prob = float(np.mean(draws))
        ci_lower = float(np.percentile(draws, 2.5))
        ci_upper = float(np.percentile(draws, 97.5))

        return {
            "probability": round(prob, 4),
            "ci_lower": round(ci_lower, 4),
            "ci_upper": round(ci_upper, 4),
        }

    @property
    def is_ready(self) -> bool:
        """True apenas quando o trace foi carregado com sucesso."""
        return self._is_loaded and self._trace is not None
