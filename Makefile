.PHONY: install lint test docker-build run external-smoke

install:
	python -m pip install -r requirements-dev.txt

lint:
	ruff check app tests tools

test:
	pytest -q

docker-build:
	docker build -t iris-inference:local .

run:
	MLFLOW_TRACKING_URI=$${MLFLOW_TRACKING_URI:-http://localhost:5000} MODEL_URI=$${MODEL_URI:-models:/iris-classifier@champion} uvicorn app.main:app --reload --port 8080

external-smoke:
	@test -n "$${BASE_URL}" || (echo "BASE_URL is required" >&2; exit 2)
	python tools/external_smoke.py --base-url "$${BASE_URL}" --requests "$${REQUESTS:-30}" --max-p95 "$${MAX_P95:-0.5}"
