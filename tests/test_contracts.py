from pathlib import Path

import yaml

from app.main import app

ROOT = Path(__file__).resolve().parents[1]
PREDICT_PATH = "/v1/models/iris:predict"


def test_openapi_contract_matches_runtime_route() -> None:
    declared = yaml.safe_load((ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8"))
    generated = app.openapi()

    assert PREDICT_PATH in declared["paths"]
    assert PREDICT_PATH in generated["paths"]
    assert "/v1/models/iris-classifier:predict" not in generated["paths"]


def test_prediction_response_contract_exposes_model_version() -> None:
    declared = yaml.safe_load((ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8"))
    response_schema = declared["components"]["schemas"]["PredictResponse"]

    assert "model_version" in response_schema["required"]
    assert response_schema["properties"]["model_version"]["type"] == "string"
