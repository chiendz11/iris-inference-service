# Iris inference service

Repository 3/3 của capstone MLOps. Repo này sở hữu **API contract, model loading,
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

## KServe và canary

1. Thay `REPLACE_ME` bằng GitHub owner và dùng image tag bất biến (commit SHA).
2. Apply `k8s/inferenceservice.yaml` cho revision ổn định.
3. Đổi image/alias trong patch canary rồi apply `k8s/inferenceservice-canary-patch.yaml`.
4. KServe chuyển 10% traffic sang revision mới trong Serverless mode.
5. Kiểm tra error rate, p95 latency và prediction distribution; chạy `scripts/promote.sh`
   hoặc `scripts/rollback.sh`.

Không dùng tag `latest` ở production; nó chỉ là placeholder dễ đọc trong template. Pipeline CD
nên thay bằng `${GITHUB_SHA}` và policy admission nên từ chối tag thay đổi được.

## Vì sao FastAPI custom predictor?

KServe có runtime MLflow dựng sẵn, nhưng custom predictor giúp capstone thể hiện rõ API validation,
health probe, Prometheus metric và cách resolve alias từ Model Registry. Đổi lại, repo phải chịu trách
nhiệm đồng bộ phiên bản `mlflow`/`scikit-learn` với môi trường training; requirements được pin để giảm rủi ro.

