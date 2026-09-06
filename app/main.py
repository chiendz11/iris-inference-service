from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.drift import DriftMonitor
from app.model import FEATURES, ModelManager
from app.schemas import PredictRequest, PredictResponse, V2InferRequest

LOGGER = logging.getLogger(__name__)
manager = ModelManager()
SERVICE_NAME = os.getenv("SERVICE_NAME", "iris-classifier")
REQUESTS = Counter("iris_prediction_requests_total", "Prediction requests", ["service", "status"])
PREDICTIONS = Counter(
    "iris_predictions_total", "Predicted Iris classes", ["service", "species"]
)
LATENCY = Histogram(
    "iris_prediction_latency_seconds", "Prediction request latency", ["service"]
)
drift_monitor = DriftMonitor(service=SERVICE_NAME)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        manager.load()
        LOGGER.info("Loaded model %s", manager.model_uri)
    except Exception:
        LOGGER.exception("Model load failed; readiness stays false")
    yield


app = FastAPI(title="Iris inference service", version="0.1.0", lifespan=lifespan)


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    if not manager.ready:
        raise HTTPException(status_code=503, detail=manager.error or "Model is not loaded")
    return {"status": "ready", "model_uri": manager.model_uri}


@app.get("/v2/health/live")
def v2_live() -> dict[str, bool]:
    return {"live": True}


@app.get("/v2/health/ready")
def v2_ready() -> dict[str, bool]:
    if not manager.ready:
        raise HTTPException(status_code=503, detail=manager.error or "Model is not loaded")
    return {"ready": True}


def _predict(rows: list[list[float]]) -> list[str]:
    start = time.perf_counter()
    try:
        predictions = manager.predict(rows)
        REQUESTS.labels(service=SERVICE_NAME, status="success").inc()
        drift_monitor.observe(rows)
        for prediction in predictions:
            PREDICTIONS.labels(service=SERVICE_NAME, species=prediction).inc()
        return predictions
    except Exception as exc:
        REQUESTS.labels(service=SERVICE_NAME, status="error").inc()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        LATENCY.labels(service=SERVICE_NAME).observe(time.perf_counter() - start)


@app.post("/v1/models/iris:predict", response_model=PredictResponse)
def predict(request: PredictRequest) -> PredictResponse:
    rows = [[getattr(instance, feature) for feature in FEATURES] for instance in request.instances]
    return PredictResponse(model_uri=manager.model_uri, predictions=_predict(rows))


@app.post("/v2/models/iris/infer")
def v2_infer(request: V2InferRequest) -> dict:
    predictions = _predict(request.inputs[0].data)
    return {
        "model_name": "iris",
        "model_version": manager.model_uri,
        "id": request.id,
        "outputs": [
            {
                "name": "predict",
                "shape": [len(predictions)],
                "datatype": "BYTES",
                "data": predictions,
            }
        ],
    }


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
