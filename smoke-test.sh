#!/usr/bin/env bash
set -euo pipefail

RUNNER_URL="${RUNNER_URL:-http://localhost:8080}"
FUNCTION_ID="${FUNCTION_ID:-test-fn-1}"
WORK_DIR="$(mktemp -d)"
PY_FILE="$WORK_DIR/main.py"

cleanup() {
  if [[ -n "${DEPLOYMENT_ID:-}" && "${DEPLOYMENT_ID}" != "null" ]]; then
    curl -s -X DELETE "$RUNNER_URL/deployments/$DEPLOYMENT_ID" >/dev/null || true
  fi
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

cat > "$PY_FILE" <<'PY'
def handler(event, context):
    return {
        "message": "ok",
        "event": event,
        "context": context,
        "sum": event.get("a", 0) + event.get("b", 0),
    }
PY

HASH="$(sha256sum "$PY_FILE" | awk '{print $1}')"

echo "== Health =="
curl -s "$RUNNER_URL/health" | jq .

echo
echo "== Deploy =="
DEPLOY_RESP="$(curl -s -X POST "$RUNNER_URL/deploy?function_id=$FUNCTION_ID&hash_code=$HASH&entry_point=main.handler&cpu_cores=0.5&memory_mb=256&pid_limit=50" \
  -F "file=@$PY_FILE;type=text/x-python")"
echo "$DEPLOY_RESP" | jq .

DEPLOYMENT_ID="$(echo "$DEPLOY_RESP" | jq -r '.deployment_id')"
if [[ -z "$DEPLOYMENT_ID" || "$DEPLOYMENT_ID" == "null" ]]; then
  echo "Deploy failed: deployment_id missing" >&2
  exit 1
fi

echo
echo "== Invoke =="
curl -s -X POST "$RUNNER_URL/invoke/$DEPLOYMENT_ID" \
  -H "Content-Type: application/json" \
  -d '{"event":{"a":2,"b":3},"context":{"request_id":"smoke-1"}}' | jq .

echo
echo "== Delete =="
curl -s -X DELETE "$RUNNER_URL/deployments/$DEPLOYMENT_ID" | jq .

DEPLOYMENT_ID=""
echo
echo "Smoke test passed"
