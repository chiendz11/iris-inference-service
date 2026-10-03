from __future__ import annotations

import time

from fastapi import HTTPException

from app.observability.metrics import LATENCY, PREDICTIONS, REQUESTS
from app.runtime import drift_monitor, manager


def predict_rows(rows: list[list[float]]) -> list[str]:
    start = time.perf_counter()
    labels = {
        "service": manager.service_name,
        "model_version": manager.model_version,
    }
    try:
        predictions = manager.predict(rows)
        REQUESTS.labels(**labels, status="success").inc()
        drift_monitor.observe(rows, model_version=manager.model_version)
        for prediction in predictions:
            PREDICTIONS.labels(**labels, species=prediction).inc()
        return predictions
    except Exception as exc:
        REQUESTS.labels(**labels, status="error").inc()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        LATENCY.labels(**labels).observe(time.perf_counter() - start)
