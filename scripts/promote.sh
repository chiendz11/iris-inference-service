#!/usr/bin/env sh
set -eu

namespace="${NAMESPACE:-iris-serving}"
service="${INFERENCE_SERVICE:-iris}"

kubectl patch inferenceservice "$service" -n "$namespace" --type merge \
  -p '{"spec":{"predictor":{"canaryTrafficPercent":100}}}'
echo "Promoted latest ready revision to 100% traffic"

