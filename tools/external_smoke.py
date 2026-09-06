from __future__ import annotations

import argparse
import json
import math
import os
import ssl
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ALLOWED_LABELS = {"setosa", "versicolor", "virginica"}


@dataclass(frozen=True)
class Sample:
    features: dict[str, float]
    expected_label: str


SAMPLES = (
    Sample(
        features={
            "sepal_length": 5.1,
            "sepal_width": 3.5,
            "petal_length": 1.4,
            "petal_width": 0.2,
        },
        expected_label="setosa",
    ),
    Sample(
        features={
            "sepal_length": 6.0,
            "sepal_width": 2.9,
            "petal_length": 4.5,
            "petal_width": 1.5,
        },
        expected_label="versicolor",
    ),
    Sample(
        features={
            "sepal_length": 6.7,
            "sepal_width": 3.1,
            "petal_length": 5.6,
            "petal_width": 2.4,
        },
        expected_label="virginica",
    ),
)


class SmokeError(RuntimeError):
    pass


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        raise ValueError("Cannot calculate a percentile from an empty list")
    ordered = sorted(values)
    index = max(0, math.ceil(percentile_value * len(ordered)) - 1)
    return ordered[index]


def request_json(
    method: str,
    url: str,
    *,
    timeout: float,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    ca_bundle: str | None = None,
) -> tuple[dict[str, Any], float]:
    headers = {"Accept": "application/json", "User-Agent": "iris-external-smoke/1.0"}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url=url, data=body, headers=headers, method=method)
    context = ssl.create_default_context(cafile=ca_bundle)
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=timeout, context=context) as response:  # nosec B310
            elapsed = time.perf_counter() - started
            content = response.read().decode("utf-8")
            if response.status < 200 or response.status >= 300:
                raise SmokeError(f"{method} {url} returned HTTP {response.status}: {content}")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SmokeError(f"{method} {url} returned HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise SmokeError(f"{method} {url} failed: {exc}") from exc

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise SmokeError(f"{method} {url} did not return JSON: {content[:200]}") from exc
    if not isinstance(parsed, dict):
        raise SmokeError(f"{method} {url} returned a non-object JSON response")
    return parsed, elapsed


def wait_until_ready(
    base_url: str,
    *,
    attempts: int,
    interval: float,
    timeout: float,
    token: str | None,
    ca_bundle: str | None,
) -> None:
    url = urljoin(f"{base_url.rstrip('/')}/", "health/ready")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response, _ = request_json(
                "GET", url, timeout=timeout, token=token, ca_bundle=ca_bundle
            )
            if response.get("status") != "ready" or not response.get("model_uri"):
                raise SmokeError(f"Unexpected readiness response: {response}")
            return
        except SmokeError as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(interval)
    raise SmokeError(f"Service was not ready after {attempts} attempts: {last_error}")


def run_smoke(
    base_url: str,
    *,
    request_count: int,
    max_p95: float,
    timeout: float,
    token: str | None,
    ca_bundle: str | None,
) -> dict[str, Any]:
    prediction_url = urljoin(f"{base_url.rstrip('/')}/", "v1/models/iris:predict")
    latencies: list[float] = []
    errors: list[str] = []
    label_counts = {label: 0 for label in sorted(ALLOWED_LABELS)}

    for index in range(request_count):
        sample = SAMPLES[index % len(SAMPLES)]
        try:
            response, elapsed = request_json(
                "POST",
                prediction_url,
                timeout=timeout,
                token=token,
                ca_bundle=ca_bundle,
                payload={"instances": [sample.features]},
            )
            predictions = response.get("predictions")
            if not isinstance(response.get("model_uri"), str):
                raise SmokeError("Prediction response is missing model_uri")
            if not isinstance(predictions, list) or len(predictions) != 1:
                raise SmokeError(f"Invalid predictions field: {predictions}")
            prediction = predictions[0]
            if prediction not in ALLOWED_LABELS:
                raise SmokeError(f"Unexpected prediction label: {prediction}")
            if prediction != sample.expected_label:
                raise SmokeError(
                    f"Expected {sample.expected_label} for sample {index + 1}, got {prediction}"
                )
            label_counts[prediction] += 1
            latencies.append(elapsed)
        except SmokeError as exc:
            errors.append(f"request {index + 1}: {exc}")

    p95 = percentile(latencies, 0.95) if latencies else math.inf
    summary = {
        "base_url": base_url.rstrip("/"),
        "requests": request_count,
        "successful": len(latencies),
        "success_rate": round(len(latencies) / request_count, 4),
        "p95_seconds": round(p95, 4) if math.isfinite(p95) else None,
        "max_p95_seconds": max_p95,
        "prediction_counts": label_counts,
        "errors": errors[:10],
    }
    if errors or p95 > max_p95:
        raise SmokeError(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate public DNS, TLS, routing and the Iris prediction contract."
    )
    parser.add_argument("--base-url", required=True, help="Example: https://api.example.com")
    parser.add_argument("--requests", type=int, default=30)
    parser.add_argument("--max-p95", type=float, default=0.5)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--ready-attempts", type=int, default=10)
    parser.add_argument("--ready-interval", type=float, default=3.0)
    parser.add_argument("--token", default=os.getenv("IRIS_API_TOKEN"))
    parser.add_argument("--ca-bundle", default=None)
    args = parser.parse_args()
    if args.requests < len(SAMPLES):
        parser.error(f"--requests must be at least {len(SAMPLES)}")
    if args.max_p95 <= 0 or args.timeout <= 0:
        parser.error("--max-p95 and --timeout must be positive")
    return args


def main() -> int:
    args = parse_args()
    try:
        wait_until_ready(
            args.base_url,
            attempts=args.ready_attempts,
            interval=args.ready_interval,
            timeout=args.timeout,
            token=args.token,
            ca_bundle=args.ca_bundle,
        )
        summary = run_smoke(
            args.base_url,
            request_count=args.requests,
            max_p95=args.max_p95,
            timeout=args.timeout,
            token=args.token,
            ca_bundle=args.ca_bundle,
        )
    except SmokeError as exc:
        print(f"external smoke FAILED\n{exc}", file=sys.stderr)
        return 1
    print("external smoke PASSED")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
