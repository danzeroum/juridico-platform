import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.cluster import MiniBatchKMeans


class AnomalyDetector:
    def __init__(self):
        self.iso_forest = IsolationForest(
            n_estimators=100,
            contamination=0.05,
            random_state=42,
        )
        self.fallback = MiniBatchKMeans(
            n_clusters=8,
            random_state=42,
        )

    def detect(self, features: np.ndarray) -> dict:
        try:
            scores = self.iso_forest.decision_function(features.reshape(1, -1))[0]
            is_anomaly = self.iso_forest.predict(features.reshape(1, -1))[0] == -1
            method = "isolation_forest"
        except Exception:
            self.fallback.fit(features.reshape(1, -1))
            scores = -self.fallback.score(features.reshape(1, -1))
            is_anomaly = scores < np.percentile([scores], 5)
            method = "kmeans_fallback"

        return {
            "anomaly_score": float(scores),
            "is_anomaly": bool(is_anomaly),
            "method": method,
        }
