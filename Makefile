.PHONY: install lint test docker-build run deploy canary

install:
	python -m pip install -r requirements-dev.txt

lint:
	ruff check app tests

test:
	pytest -q

docker-build:
	docker build -t iris-inference:local .

run:
	MLFLOW_TRACKING_URI=$${MLFLOW_TRACKING_URI:-http://localhost:5000} MODEL_URI=$${MODEL_URI:-models:/iris-classifier@champion} uvicorn app.main:app --reload --port 8080

deploy:
	kubectl apply -f k8s/namespace.yaml
	kubectl apply -f k8s/inferenceservice.yaml

canary:
	kubectl apply -f k8s/inferenceservice-canary-patch.yaml

