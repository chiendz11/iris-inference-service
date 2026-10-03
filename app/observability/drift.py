from __future__ import annotations

import threading
from collections import deque

import numpy as np
from prometheus_client import Gauge, Histogram

from app.model import FEATURES

# Statistics of sklearn's canonical Iris training set. They form a tiny, transparent
# reference profile; a larger platform should version a richer profile with the model.
REFERENCE_MEAN = np.array([5.8433, 3.0573, 3.7580, 1.1993])
REFERENCE_STD = np.array([0.8253, 0.4344, 1.7594, 0.7597])

FEATURE_VALUE = Histogram(
    "iris_feature_value",
    "Observed feature distribution",
    ["service", "model_version", "feature"],
    buckets=(0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0),
)
FEATURE_MEAN = Gauge(
    "iris_feature_window_mean", "Rolling feature mean", ["service", "model_version", "feature"]
)
DRIFT_ZSCORE = Gauge(
    "iris_feature_drift_zscore",
    "Absolute shift of rolling mean in reference standard deviations",
    ["service", "model_version", "feature"],
)
DRIFT_DETECTED = Gauge(
    "iris_data_drift_detected",
    "1 when any feature exceeds the configured drift threshold",
    ["service", "model_version"],
)


class DriftMonitor:
    def __init__(
        self,
        service: str,
        window_size: int,
        min_samples: int,
        threshold: float,
    ) -> None:
        self.service = service
        self.window = deque(maxlen=window_size)
        self.min_samples = min_samples
        self.threshold = threshold
        self._lock = threading.Lock()

    def observe(self, rows: list[list[float]], *, model_version: str) -> None:
        with self._lock:
            for row in rows:
                values = np.asarray(row, dtype=float)
                self.window.append(values)
                for feature, value in zip(FEATURES, values, strict=True):
                    FEATURE_VALUE.labels(
                        service=self.service, model_version=model_version, feature=feature
                    ).observe(value)
            if len(self.window) < self.min_samples:
                DRIFT_DETECTED.labels(
                    service=self.service, model_version=model_version
                ).set(0)
                return
            means = np.asarray(self.window).mean(axis=0)
            zscores = np.abs((means - REFERENCE_MEAN) / REFERENCE_STD)
            for feature, mean, zscore in zip(FEATURES, means, zscores, strict=True):
                labels = {
                    "service": self.service,
                    "model_version": model_version,
                    "feature": feature,
                }
                FEATURE_MEAN.labels(**labels).set(mean)
                DRIFT_ZSCORE.labels(**labels).set(zscore)
            DRIFT_DETECTED.labels(service=self.service, model_version=model_version).set(
                float(np.any(zscores > self.threshold))
            )
