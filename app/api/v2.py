from fastapi import APIRouter, HTTPException

from app.model.predictor import predict_rows
from app.runtime import manager
from app.schemas import V2InferRequest

router = APIRouter(prefix="/v2", tags=["kserve-v2"])


@router.get("/health/live")
def live() -> dict[str, bool]:
    return {"live": True}


@router.get("/health/ready")
def ready() -> dict[str, bool]:
    if not manager.ready:
        raise HTTPException(status_code=503, detail=manager.error or "Model is not loaded")
    return {"ready": True}


@router.post("/models/iris/infer")
def infer(request: V2InferRequest) -> dict:
    predictions = predict_rows(request.inputs[0].data)
    return {
        "model_name": "iris",
        "model_version": manager.model_version,
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
