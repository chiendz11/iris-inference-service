from fastapi.testclient import TestClient

from app.main import app, manager


class FakeModel:
    def predict(self, frame):
        return ["setosa" if row.petal_length < 2 else "virginica" for row in frame.itertuples()]


def setup_module():
    manager.model = FakeModel()
    manager.error = None
    manager.model_uri = "models:/iris-classifier@champion"
    manager.model_version = "12"


client = TestClient(app)


def test_live_and_ready():
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200


def test_v1_prediction_contract():
    response = client.post(
        "/v1/models/iris:predict",
        json={
            "instances": [
                {
                    "sepal_length": 5.1,
                    "sepal_width": 3.5,
                    "petal_length": 1.4,
                    "petal_width": 0.2,
                }
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["predictions"] == ["setosa"]
    assert response.json()["model_version"] == "12"


def test_v2_prediction_contract():
    response = client.post(
        "/v2/models/iris/infer",
        json={
            "id": "demo-1",
            "inputs": [
                {
                    "name": "input-0",
                    "shape": [1, 4],
                    "datatype": "FP64",
                    "data": [[6.3, 3.3, 6.0, 2.5]],
                }
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["outputs"][0]["data"] == ["virginica"]
    assert response.json()["model_version"] == "12"


def test_rejects_wrong_feature_count():
    response = client.post(
        "/v2/models/iris/infer",
        json={"inputs": [{"shape": [1, 3], "datatype": "FP64", "data": [[1, 2, 3]]}]},
    )
    assert response.status_code == 422


def test_classifier_alias_is_not_an_api_route():
    response = client.post(
        "/v1/models/iris-classifier:predict",
        json={"instances": []},
    )
    assert response.status_code == 404


def test_metrics_identify_immutable_model_version():
    client.post(
        "/v1/models/iris:predict",
        json={
            "instances": [
                {
                    "sepal_length": 5.1,
                    "sepal_width": 3.5,
                    "petal_length": 1.4,
                    "petal_width": 0.2,
                }
            ]
        },
    )
    metrics = client.get("/metrics").text
    assert 'model_version="12"' in metrics
    assert 'service="iris-classifier"' in metrics
