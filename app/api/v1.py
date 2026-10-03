from fastapi import APIRouter

from app.model import FEATURES
from app.model.predictor import predict_rows
from app.runtime import manager
from app.schemas import PredictRequest, PredictResponse

router = APIRouter(prefix="/v1/models/iris", tags=["prediction-v1"])


@router.post(":predict", response_model=PredictResponse)
def predict(request: PredictRequest) -> PredictResponse:
    rows = [[getattr(instance, feature) for feature in FEATURES] for instance in request.instances]
    return PredictResponse(
        model_uri=manager.model_uri,
        model_version=manager.model_version,
        predictions=predict_rows(rows),
    )
