from prometheus_client import Counter, Histogram

REQUESTS = Counter(
    "iris_prediction_requests_total",
    "Prediction requests",
    ["service", "model_version", "status"],
)
PREDICTIONS = Counter(
    "iris_predictions_total",
    "Predicted Iris classes",
    ["service", "model_version", "species"],
)
LATENCY = Histogram(
    "iris_prediction_latency_seconds",
    "Prediction request latency",
    ["service", "model_version"],
)
