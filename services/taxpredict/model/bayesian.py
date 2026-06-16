import pymc as pm
import numpy as np
import pandas as pd


class TaxPredictionModel:
    def __init__(self, materia: str):
        self.materia = materia
        self.trace = None

    def fit(self, data: pd.DataFrame):
        with pm.Model() as model:
            mu_national = pm.Normal("mu_national", mu=0.3, sigma=0.15)
            sigma_tribunal = pm.HalfNormal("sigma_tribunal", sigma=0.1)
            # TODO: adaptar dims/coords e likelihood completos na Fase 3
            beta_valor = pm.Normal("beta_valor", mu=0, sigma=0.1)
            beta_recencia = pm.Normal("beta_recencia", mu=0, sigma=0.1)
            beta_economico = pm.Normal("beta_economico", mu=0, sigma=0.05)

            # Placeholder para evitar implementacao incompleta agora
            p = pm.math.sigmoid(
                mu_national
                + beta_valor * data["valor_log"]
                + beta_recencia * data["recencia"]
                + beta_economico * data["indicador_economico"]
            )
            pm.Bernoulli("obs", p=p, observed=data["sucesso"])

            self.trace = pm.sample(
                draws=100, tune=100, chains=2,
                target_accept=0.9, random_seed=42,
                progressbar=False,
            )

    def predict(self) -> dict:
        # TODO: sample_posterior_predictive com caso real na Fase 3
        return {
            "probability": 0.65,
            "ci_lower": 0.52,
            "ci_upper": 0.77,
        }
