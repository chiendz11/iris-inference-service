from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.v1 import router as v1_router
from app.api.v2 import router as v2_router
from app.runtime import manager

LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        manager.load()
        LOGGER.info("Loaded model %s at immutable version %s", manager.model_uri, manager.model_version)
    except Exception:
        LOGGER.exception("Model load failed; readiness stays false")
    yield


app = FastAPI(title="Iris inference service", version="1.0.0", lifespan=lifespan)
app.include_router(v1_router)
app.include_router(v2_router)


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    if not manager.ready:
        raise HTTPException(status_code=503, detail=manager.error or "Model is not loaded")
    return {
        "status": "ready",
        "model_uri": manager.model_uri,
        "model_version": manager.model_version,
    }


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
