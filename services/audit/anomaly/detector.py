"""
Detector de anomalias contábeis (ContabilIA — Fase 2).

BUGS CORRIGIDOS:
- fit() e detect() estão separados (antes, detect() chamava decision_function()
  sem fit() prévio, o que causava RuntimeError em runtime).
- Fallback MiniBatchKMeans: a lógica anterior comparava um escalar com o
  percentil de si mesmo (sempre True). Agora compara com o percentil da
  distribuição de treino armazenada em _fallback_threshold.

USO CORRETO:
    detector = AnomalyDetector()
    detector.fit(X_historico)          # treinar uma vez (em Celery Beat)
    resultado = detector.detect(x_novo)  # usar em runtime
"""
from __future__ import annotations

import numpy as np
from sklearn.cluster import MiniBatchKMeans
from sklearn.ensemble import IsolationForest


class AnomalyDetector:
    def __init__(self, contamination: float = 0.05, n_clusters: int = 8) -> None:
        self.contamination = contamination
        self.iso_forest = IsolationForest(
            n_estimators=100,
            contamination=contamination,
            random_state=42,
        )
        self.fallback = MiniBatchKMeans(
            n_clusters=n_clusters,
            random_state=42,
        )
        self._is_fitted = False
        self._fallback_threshold: float | None = None

    def fit(self, X_train: np.ndarray) -> "AnomalyDetector":
        """
        Treina em dados históricos. Deve ser chamado ANTES de detect().
        Em produção, chamar periodicamente via Celery Beat (não em cada request).
        """
        self.iso_forest.fit(X_train)
        self.fallback.fit(X_train)
        # Calcular threshold como (1 - contamination) percentil das distâncias de treino
        # → por definição, contamination% dos pontos de treino ficam acima do threshold
        train_distances = self.fallback.transform(X_train).min(axis=1)
        percentile = (1.0 - self.contamination) * 100
        self._fallback_threshold = float(np.percentile(train_distances, percentile))
        self._is_fitted = True
        return self

    def detect(self, features: np.ndarray) -> dict:
        """
        Detecta anomalia em um único vetor de features.
        Requer fit() prévio; levanta RuntimeError se não treinado.
        """
        if not self._is_fitted:
            raise RuntimeError(
                "AnomalyDetector.fit() deve ser chamado antes de detect(). "
                "Treine em dados históricos antes de usar em runtime."
            )

        x = features.reshape(1, -1)
        try:
            score = float(self.iso_forest.decision_function(x)[0])
            is_anomaly = bool(self.iso_forest.predict(x)[0] == -1)
            method = "isolation_forest"
        except Exception:
            # Fallback: distância ao centroide mais próximo vs distribuição de treino
            dist = float(self.fallback.transform(x).min(axis=1)[0])
            is_anomaly = dist > self._fallback_threshold  # type: ignore[operator]
            # Normalizar para escala comparável ao IsolationForest (negativo = anomalia)
            score = self._fallback_threshold - dist  # type: ignore[operator]
            method = "kmeans_fallback"

        return {
            "anomaly_score": score,
            "is_anomaly": is_anomaly,
            "method": method,
        }
