from __future__ import annotations

import re
import threading

import mlflow
import pandas as pd
from mlflow import MlflowClient

from app.config import Settings

FEATURES = ["sepal_length", "sepal_width", "petal_length", "petal_width"]
ALIAS_MODEL_URI = re.compile(r"^models:/([^/@]+)@([^/]+)$")


class ModelManager:
    def __init__(self, settings: Settings) -> None:
        self.service_name = settings.service_name
        self.model_uri = settings.model_uri
        self.tracking_uri = settings.mlflow_tracking_uri
        self.model_version = settings.model_version or "unresolved"
        self.model = None
        self.error: str | None = None
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self.model is not None

    def _resolve_model_version(self) -> str:
        match = ALIAS_MODEL_URI.fullmatch(self.model_uri)
        if match is None:
            return self.model_uri
        model_name, alias = match.groups()
        version = MlflowClient(tracking_uri=self.tracking_uri).get_model_version_by_alias(
            model_name, alias
        )
        return str(version.version)

    def load(self) -> None:
        with self._lock:
            mlflow.set_tracking_uri(self.tracking_uri)
            try:
                # GitOps injects MODEL_VERSION for a stable canary identity. Local
                # alias-based runs resolve the immutable version from MLflow.
                if self.model_version == "unresolved":
                    self.model_version = self._resolve_model_version()
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
