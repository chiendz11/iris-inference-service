from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str
    model_uri: str
    model_version: str | None
    mlflow_tracking_uri: str
    drift_window_size: int
    drift_min_samples: int
    drift_zscore_threshold: float

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            service_name=os.getenv("SERVICE_NAME", "iris-classifier"),
            model_uri=os.getenv("MODEL_URI", "models:/iris-classifier@champion"),
            model_version=os.getenv("MODEL_VERSION") or None,
            mlflow_tracking_uri=os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"),
            drift_window_size=int(os.getenv("DRIFT_WINDOW_SIZE", "200")),
            drift_min_samples=int(os.getenv("DRIFT_MIN_SAMPLES", "30")),
            drift_zscore_threshold=float(os.getenv("DRIFT_ZSCORE_THRESHOLD", "3.0")),
        )


settings = Settings.from_environment()
