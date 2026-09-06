# Iris inference service (repo 3/5)

Repository 3/4 của capstone MLOps. Repo này sở hữu **API contract, model loading,
runtime container, metrics và KServe deployment**. Nó không chứa training code hoặc database.

Service tải model qua URI `models:/iris-classifier@champion`. Alias tách deployment khỏi số
version cụ thể: training pipeline có thể promote model mới, còn API contract vẫn ổn định.

## Chạy local

Sau khi `model-registry` chạy và `data-pipeline` đã tạo alias `champion`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export MLFLOW_TRACKING_URI=http://localhost:5000
export MODEL_URI='models:/iris-classifier@champion'
uvicorn app.main:app --port 8080
```

```bash
curl http://localhost:8080/health/ready
curl -X POST http://localhost:8080/v1/models/iris:predict \
  -H 'content-type: application/json' \
  -d '{"instances":[{"sepal_length":5.1,"sepal_width":3.5,"petal_length":1.4,"petal_width":0.2}]}'
```

Metrics Prometheus ở `GET /metrics`. Dịch vụ cũng có KServe V2 endpoint
`POST /v2/models/iris/infer` để minh họa data-plane protocol.

## External smoke từ máy local

Sau khi Route53, TLS, NLB, Kourier và KServe đã sẵn sàng, chạy trực tiếp từ laptop:

```bash
python tools/external_smoke.py \
  --base-url https://api.example.com \
  --requests 30 \
  --max-p95 0.5
```

Hoặc dùng Makefile:

```bash
BASE_URL=https://api.example.com make external-smoke
```

Script kiểm tra readiness, TLS/DNS/routing từ bên ngoài cluster, response schema, ba nhãn Iris,
success rate và p95 latency. Nếu API có bearer token, đặt `IRIS_API_TOKEN` trong environment.
Không cần frontend riêng hoặc GitHub Actions `workflow_dispatch`; chạy từ máy local đã là một phép
kiểm tra external end-to-end có chủ đích.

## KServe trên EKS và canary

1. GitHub Actions test/build, nhận quyền AWS qua OIDC và push SHA tag lên ECR.
2. Workflow tạo pull request cập nhật image SHA trong repo `iris-gitops`.
3. Sau review/merge, Argo CD reconcile KServe production.
4. Data pipeline đổi `MODEL_URI` sang alias `candidate`; thay đổi pod spec tạo Knative revision.
5. `canaryTrafficPercent=10`; chỉ khi online SLO đạt mới đổi MLflow champion và lên 100%.
6. Không đạt thì traffic canary về 0.

KServe canary ở đây dùng Serverless/Knative. ECR Terraform bật immutable tag và scan-on-push;
workflow dùng `${GITHUB_SHA}`, không dùng `latest`.

## Observability và drift

- `iris_prediction_requests_total`: tính RPS/error rate.
- `iris_prediction_latency_seconds`: histogram và p95.
- `iris_predictions_total{species}`: phân phối nhãn dự đoán.
- `iris_feature_value`, `iris_feature_window_mean`: phân phối/mean feature.
- `iris_feature_drift_zscore`, `iris_data_drift_detected`: drift cơ bản trên rolling window.

Production PodMonitor, PrometheusRule và dashboard nằm trong
`iris-gitops/environments/production/inference-service`. Drift này là cảnh báo đơn giản, không thay thế
PSI/KS-test có reference profile được version hóa khi hệ thống lớn hơn.

## Vì sao FastAPI custom predictor?

KServe có runtime MLflow dựng sẵn, nhưng custom predictor giúp capstone thể hiện rõ API validation,
health probe, Prometheus metric và cách resolve alias từ Model Registry. Đổi lại, repo phải chịu trách
nhiệm đồng bộ phiên bản `mlflow`/`scikit-learn` với môi trường training; requirements được pin để giảm rủi ro.

GitHub environment `prod` variables: `AWS_REGION`, `AWS_DEPLOY_ROLE_ARN`,
`INFERENCE_ECR_REPOSITORY`, `GITOPS_REPOSITORY`, `GITOPS_APP_CLIENT_ID`; secret
`GITOPS_APP_PRIVATE_KEY`. Workflow chỉ mint token ngắn hạn có quyền tạo branch/PR ở
`iris-gitops`, không lưu PAT dài hạn.
