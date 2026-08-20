#!/usr/bin/env sh
set -eu

namespace="${NAMESPACE:-iris-serving}"
service="${INFERENCE_SERVICE:-iris}"

kubectl patch inferenceservice "$service" -n "$namespace" --type merge \
  -p '{"spec":{"predictor":{"canaryTrafficPercent":0}}}'
echo "Rolled traffic back to the last known-good revision"

