from __future__ import annotations

import os
import threading

import mlflow
import pandas as pd


FEATURES = ["sepal_length", "sepal_width", "petal_length", "petal_width"]


class ModelManager:
    def __init__(self) -> None:
        self.model_uri = os.getenv("MODEL_URI", "models:/iris-classifier@champion")
        self.tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
        self.model = None
        self.error: str | None = None
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self.model is not None

    def load(self) -> None:
        with self._lock:
            mlflow.set_tracking_uri(self.tracking_uri)
            try:
                self.model = mlflow.pyfunc.load_model(self.model_uri)
                self.error = None
            except Exception as exc:
                self.model = None
                self.error = str(exc)
                raise

    def predict(self, rows: list[list[float]]) -> list[str]:
        if self.model is None:
            raise RuntimeError("Model is not loaded")
        frame = pd.DataFrame(rows, columns=FEATURES)
        return [str(value) for value in self.model.predict(frame)]

