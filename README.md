# Iris inference service (repo 3/5)

Repo này là source of truth cho **serving runtime, API/schema và telemetry của API**. Nó không
sở hữu manifest production, KServe, Kubernetes, Argo CD hay cách repo GitOps biểu diễn image.

## Ownership

```text
iris-inference-service
├── app/api/              versioned HTTP routes
├── app/model/            MLflow loader and prediction behavior
├── app/observability/    request, latency, distribution and drift metrics
├── contracts/            public OpenAPI + runtime-config schema
├── release/              reviewed production config and secret references
├── tests/                API, contract, metrics and ownership regression tests
└── tools/                developer-operated external smoke client
```

Production desired state nằm duy nhất trong `iris-gitops`. AWS/ECR/IAM nằm trong
`iris-infrastructure`. Production smoke/canary evaluation nằm trong automation image do
`iris-gitops` sở hữu; `tools/external_smoke.py` chỉ là client tiện dụng để developer kiểm tra từ
laptop.

## Chạy local

Sau khi MLflow local chạy và model đã có alias `champion`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export MLFLOW_TRACKING_URI=http://localhost:5000
export MODEL_URI='models:/iris-classifier@champion'
uvicorn app.main:app --port 8080
```

API v1 chuẩn duy nhất là `/v1/models/iris:predict`:

```bash
curl http://localhost:8080/health/ready
curl -X POST http://localhost:8080/v1/models/iris:predict \
  -H 'content-type: application/json' \
  -d '{"instances":[{"sepal_length":5.1,"sepal_width":3.5,"petal_length":1.4,"petal_width":0.2}]}'
```

`contracts/openapi.yaml` là contract review được của endpoint này. Service cũng giữ KServe V2
data-plane endpoint `POST /v2/models/iris/infer`.

## Model identity và observability

GitOps rollout truyền `MODEL_VERSION` bất biến vào candidate revision. Nếu chạy local mà không có
biến này, loader resolve version đằng sau MLflow alias lúc khởi động. Readiness, prediction response
và toàn bộ metric đều công bố `model_version`, nhờ đó canary evaluator có thể lọc candidate thay vì
trộn metric baseline và candidate:

- `iris_prediction_requests_total{service,model_version,status}`;
- `iris_prediction_latency_seconds{service,model_version}`;
- `iris_predictions_total{service,model_version,species}`;
- feature distribution và drift gauges có cùng `service,model_version`.

Metrics ở `GET /metrics`. Drift hiện là rolling mean/z-score cơ bản; hệ thống lớn hơn nên version
hóa reference profile cùng model và bổ sung PSI/KS-test.

## Workload release không biết GitOps layout

Sau merge vào `main`, CI thực hiện:

```text
test + contract checks
        ↓
build image từ pinned base
        ↓
Trivy critical-vulnerability gate
        ↓
OIDC push SHA tag vào ECR
        ↓
resolve image digest
        ↓
Cosign keyless sign repository@digest
        ↓
workflow_dispatch workload-release.yml với workload-release/v1 contract
```

CI phân loại thay đổi trước khi release:

- chỉ đổi `app/`, runtime dependency hoặc Dockerfile: gửi image digest cùng schema compatibility
  metadata, nhưng không ghi lại runtime config không đổi;
- chỉ đổi schema hoặc `release/production-runtime-config.json`: gửi config-only intent, không push
  image mới; chỉ đổi `release/production-secret-refs.json` thì gửi secret-ref-only intent;
- nếu image mới cần config mới, cùng một PR app phải đổi cả code lẫn schema/value; CI phát **một
  intent atomic** chứa image và runtime config;
- thay đổi tests/docs: không phát hành production workload.

`release/config-schema-version.txt` chọn schema đang active (hiện là `v1`), file
`contracts/runtime-config-<version>.schema.json` định nghĩa type/range/required key, còn
`release/production-runtime-config.json` là giá trị production được review. GitOps chỉ nhận schema
version + digest và values, rồi đối chiếu với bản schema đã phê duyệt trước khi render. File
`release/production-secret-refs.json` chỉ chứa tên/property của AWS Secrets Manager, tuyệt đối không
chứa secret value.

Intent mang `component=inference`, artifact/config, source repo/SHA và change ID. Workflow không
checkout `iris-gitops`, không biết `inferenceservice.yaml` ở đâu và không tự tạo deployment PR.
Renderer thuộc `iris-gitops` mới validate ECR allow-list, schema, sửa desired state và mở protected
PR. Với image-only, renderer đối chiếu `required_config` với schema đã duyệt rồi validate config đang
có trong desired state; image không tương thích sẽ bị chặn trước khi mở PR. Receiver cũng verify
chữ ký Cosign phải đến đúng workflow `iris-inference-service/.github/workflows/ci.yml@main`.
Khi nâng lên `v2`, thêm schema bất biến mới, review bản `inference-v2` tương ứng ở GitOps rồi đổi
con trỏ cùng values trong app PR; không sửa nghĩa của `v1` đã phát hành.

GitHub Environment `prod` cần các variables:

- `AWS_REGION`, `AWS_DEPLOY_ROLE_ARN`, `INFERENCE_ECR_REPOSITORY`;
- `GITOPS_REPOSITORY` (dạng `owner/iris-gitops`);
- `INTENT_PUBLISHER_APP_CLIENT_ID`.

Secret duy nhất cho cross-repo intent là `INTENT_PUBLISHER_APP_PRIVATE_KEY`, nhưng giá trị phải là
key riêng của App `iris-inference-publisher`, không dùng chung với repo khác. GitHub App chỉ cần
`Actions: write` trên `iris-gitops`; app CI không nhận `Contents: write` hoặc Pull Requests permission.

## External smoke từ máy local

Sau khi domain/TLS/KServe sẵn sàng:

```bash
python tools/external_smoke.py \
  --base-url https://api.example.com \
  --requests 30 \
  --max-p95 0.5
```

Hoặc `BASE_URL=https://api.example.com make external-smoke`. Script kiểm tra readiness,
TLS/DNS/routing, schema, ba nhãn Iris, success rate và p95. Nếu API có bearer token, đặt
`IRIS_API_TOKEN` trong environment; không cần tạo frontend chỉ để phát traffic kiểm thử.
