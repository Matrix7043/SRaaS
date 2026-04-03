#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────
# SCaaS Spring Boot API - End-to-End Test Script
# ─────────────────────────────────────────────

BASE_URL="${BASE_URL:-http://localhost:8081}"
RUNNER_URL="${RUNNER_URL:-http://localhost:8080}"
WORK_DIR="$(mktemp -d)"
TOKEN=""
REFRESH_TOKEN=""
FN_ID_1="" # function with artifact + deployed
FN_ID_2="" # function without artifact
FN_ID_3="" # function with custom config, updated, then deleted

EMAIL_1="user1@scaas1-test.com"
EMAIL_2="user2@scaas1-test.com"
PASSWORD="password123"

# ─── helpers ──────────────────────────────────

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}✓ $1${NC}"; }
fail() {
  echo -e "${RED}✗ $1${NC}"
  exit 1
}
section() { echo -e "\n${YELLOW}══ $1 ══${NC}"; }

assert_status() {
  local label="$1" expected="$2" actual="$3"
  if [[ "$actual" == "$expected" ]]; then
    pass "$label (HTTP $actual)"
  else
    fail "$label — expected HTTP $expected, got $actual"
  fi
}

cleanup() {
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

# Write a sample Python function file
PY_FILE="$WORK_DIR/handler.py"
cat >"$PY_FILE" <<'PY'
import logging

def handler(event, context):
    logging.info("handler called with event: %s", event)
    return {
        "message": "hello from SCaaS",
        "sum": event.get("a", 0) + event.get("b", 0),
        "event": event,
    }
PY

PY_FILE_V2="$WORK_DIR/handler_v2.py"
cat >"$PY_FILE_V2" <<'PY'
def handler(event, context):
    return {
        "version": 2,
        "product": event.get("x", 1) * event.get("y", 1),
    }
PY

# ─────────────────────────────────────────────
section "1. AUTH — Register two users"
# ─────────────────────────────────────────────

echo "Registering user 1..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"user11\",\"firstName\":\"Alice\",\"lastName\":\"Smith\",\"email\":\"$EMAIL_1\",\"password\":\"$PASSWORD\"}")
assert_status "Register user 1" 201 "$STATUS"

echo "Registering user 2..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"user22\",\"firstName\":\"Bob\",\"lastName\":\"Jones\",\"email\":\"$EMAIL_2\",\"password\":\"$PASSWORD\"}")
assert_status "Register user 22" 201 "$STATUS"

echo "Registering duplicate user 1 (should fail 400)..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"user1\",\"firstName\":\"Alice\",\"lastName\":\"Smith\",\"email\":\"$EMAIL_1\",\"password\":\"$PASSWORD\"}")
assert_status "Duplicate registration rejected" 400 "$STATUS"

# ─────────────────────────────────────────────
section "2. AUTH — Login"
# ─────────────────────────────────────────────

echo "Logging in as user 1..."
LOGIN_RESP=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL_1\",\"password\":\"$PASSWORD\"}")
echo "$LOGIN_RESP" | jq .
TOKEN=$(echo "$LOGIN_RESP" | jq -r '.accessToken')
REFRESH_TOKEN=$(echo "$LOGIN_RESP" | jq -r '.refreshToken')
[[ -n "$TOKEN" && "$TOKEN" != "null" ]] || fail "Login failed — no access token"
pass "Login user 1"

echo "Login with wrong password (should fail 401)..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL_1\",\"password\":\"wrongpassword\"}")
assert_status "Wrong password rejected" 401 "$STATUS"

echo "Unauthenticated request to /functions (should fail 401)..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/functions")
assert_status "Unauthenticated request rejected" 401 "$STATUS"

# ─────────────────────────────────────────────
section "3. FUNCTIONS — Create"
# ─────────────────────────────────────────────

echo "Creating function 1 (default config)..."
RESP=$(curl -s -X POST "$BASE_URL/functions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"fn-with-artifact","runtime":"PYTHON","entryPoint":"main.handler"}')
echo "$RESP" | jq .
FN_ID_1=$(echo "$RESP" | jq -r '.id')
[[ -n "$FN_ID_1" && "$FN_ID_1" != "null" ]] || fail "Function 1 creation failed"
pass "Function 1 created: $FN_ID_1"

echo "Creating function 2 (no artifact, custom resources)..."
RESP=$(curl -s -X POST "$BASE_URL/functions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"fn-no-artifact","runtime":"PYTHON","entryPoint":"main.handler","cpuCores":1.0,"mem":512,"pids":30}')
echo "$RESP" | jq .
FN_ID_2=$(echo "$RESP" | jq -r '.id')
[[ -n "$FN_ID_2" && "$FN_ID_2" != "null" ]] || fail "Function 2 creation failed"
pass "Function 2 created: $FN_ID_2"

echo "Creating function 3 (to be updated then deleted)..."
RESP=$(curl -s -X POST "$BASE_URL/functions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"fn-to-delete","runtime":"PYTHON"}')
echo "$RESP" | jq .
FN_ID_3=$(echo "$RESP" | jq -r '.id')
[[ -n "$FN_ID_3" && "$FN_ID_3" != "null" ]] || fail "Function 3 creation failed"
pass "Function 3 created: $FN_ID_3"

echo "Creating function with invalid runtime (should fail 400)..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/functions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"bad-fn","runtime":"NODEJS"}')
assert_status "Invalid runtime rejected" 400 "$STATUS"

echo "Creating function with blank name (should fail 400)..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/functions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"","runtime":"PYTHON"}')
assert_status "Blank name rejected" 400 "$STATUS"

# ─────────────────────────────────────────────
section "4. FUNCTIONS — List and Get"
# ─────────────────────────────────────────────

echo "Listing all functions (page 0, size 10)..."
RESP=$(curl -s "$BASE_URL/functions?page=0&size=10" \
  -H "Authorization: Bearer $TOKEN")
echo "$RESP" | jq '{totalElements, totalPages, content: [.content[] | {id, name, deploymentStatus}]}'
COUNT=$(echo "$RESP" | jq '.totalElements')
[[ "$COUNT" -ge 3 ]] || fail "Expected at least 3 functions, got $COUNT"
pass "List functions ($COUNT total)"

echo "Listing with small page size (page 0, size 2)..."
RESP=$(curl -s "$BASE_URL/functions?page=0&size=2" \
  -H "Authorization: Bearer $TOKEN")
echo "$RESP" | jq '{totalElements, totalPages, pageSize: .size}'
pass "Pagination works"

echo "Getting function 1 by ID..."
RESP=$(curl -s "$BASE_URL/functions/$FN_ID_1" \
  -H "Authorization: Bearer $TOKEN")
echo "$RESP" | jq .
assert_status "Get function 1" 200 "$(curl -s -o /dev/null -w "%{http_code}" \
  "$BASE_URL/functions/$FN_ID_1" -H "Authorization: Bearer $TOKEN")"

echo "Getting nonexistent function (should fail 404)..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  "$BASE_URL/functions/00000000-0000-0000-0000-000000000000" \
  -H "Authorization: Bearer $TOKEN")
assert_status "Nonexistent function returns 404" 404 "$STATUS"

echo "Checking function 1 has no artifact yet..."
HAS_ARTIFACT=$(curl -s "$BASE_URL/functions/$FN_ID_1" \
  -H "Authorization: Bearer $TOKEN" | jq '.hasArtifact')
[[ "$HAS_ARTIFACT" == "false" ]] || fail "Expected hasArtifact=false before upload"
pass "Function 1 has no artifact (correct)"

# ─────────────────────────────────────────────
section "5. FUNCTIONS — Update"
# ─────────────────────────────────────────────

echo "Updating function 3 name and resources..."
RESP=$(curl -s -X PATCH "$BASE_URL/functions/$FN_ID_3" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"fn-renamed","cpuCores":2.0,"mem":1024,"pids":64}')
echo "$RESP" | jq .
UPDATED_NAME=$(echo "$RESP" | jq -r '.name')
[[ "$UPDATED_NAME" == "fn-renamed" ]] || fail "Name not updated"
pass "Function 3 updated"

echo "Updating with invalid CPU (should fail 400)..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "$BASE_URL/functions/$FN_ID_1" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"cpuCores":0.1}')
assert_status "Invalid CPU cores rejected" 400 "$STATUS"

echo "Updating with oversized name (should fail 400)..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "$BASE_URL/functions/$FN_ID_1" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"$(python3 -c 'print("a"*101)')\"}")
assert_status "Oversized name rejected" 400 "$STATUS"

# ─────────────────────────────────────────────
section "6. ARTIFACTS — Upload"
# ─────────────────────────────────────────────

echo "Uploading artifact to function 1..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  "$BASE_URL/functions/$FN_ID_1/artifacts" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$PY_FILE;type=text/x-python")
assert_status "Artifact uploaded" 200 "$STATUS"

echo "Checking function 1 now has artifact..."
HAS_ARTIFACT=$(curl -s "$BASE_URL/functions/$FN_ID_1" \
  -H "Authorization: Bearer $TOKEN" | jq '.hasArtifact')
[[ "$HAS_ARTIFACT" == "true" ]] || fail "Expected hasArtifact=true after upload"
pass "hasArtifact=true confirmed"

echo "Uploading same artifact again (should fail 400 — no changes)..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  "$BASE_URL/functions/$FN_ID_1/artifacts" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$PY_FILE;type=text/x-python")
assert_status "Duplicate artifact rejected" 400 "$STATUS"

echo "Uploading a non-.py file (should fail 400)..."
echo "not python" >"$WORK_DIR/bad.js"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  "$BASE_URL/functions/$FN_ID_1/artifacts" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$WORK_DIR/bad.js;type=text/javascript")
assert_status "Non-.py artifact rejected" 400 "$STATUS"

echo "Uploading updated artifact (v2) to function 1..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  "$BASE_URL/functions/$FN_ID_1/artifacts" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$PY_FILE_V2;type=text/x-python")
assert_status "Updated artifact accepted" 200 "$STATUS"

echo "Confirming status changed to OUTDATED after re-upload..."
STATUS_FIELD=$(curl -s "$BASE_URL/functions/$FN_ID_1" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.deploymentStatus')
[[ "$STATUS_FIELD" == "OUTDATED" || "$STATUS_FIELD" == "NOT_DEPLOYED" ]] ||
  fail "Expected OUTDATED or NOT_DEPLOYED, got $STATUS_FIELD"
pass "Deployment status: $STATUS_FIELD"

# ─────────────────────────────────────────────
section "7. DEPLOY — Deploy function without artifact (should fail)"
# ─────────────────────────────────────────────

echo "Deploying function 2 (no artifact — should fail 404)..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  "$BASE_URL/functions/$FN_ID_2/deploy" \
  -H "Authorization: Bearer $TOKEN")
assert_status "Deploy without artifact fails 404" 404 "$STATUS"

# ─────────────────────────────────────────────
section "8. DEPLOY — Deploy function 1"
# ─────────────────────────────────────────────

echo "Deploying function 1 (has artifact)..."
RESP=$(curl -s -X POST "$BASE_URL/functions/$FN_ID_1/deploy" \
  -H "Authorization: Bearer $TOKEN")
echo "$RESP" | jq .
DEPLOY_STATUS=$(echo "$RESP" | jq -r '.status')
INVOCATION_URL=$(echo "$RESP" | jq -r '.invocationURL')
[[ "$DEPLOY_STATUS" == "DEPLOYED" ]] || fail "Expected DEPLOYED, got $DEPLOY_STATUS"
[[ -n "$INVOCATION_URL" && "$INVOCATION_URL" != "null" ]] || fail "No invocation URL returned"
pass "Function 1 deployed — invocation URL: $INVOCATION_URL"

INVOKE_URL="$INVOCATION_URL"
if [[ "$INVOKE_URL" != http://* && "$INVOKE_URL" != https://* ]]; then
  INVOKE_URL="$RUNNER_URL$INVOKE_URL"
fi

echo "Invoking deployed function 1..."
RESP=$(curl -s -X POST "$INVOKE_URL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"event":{"x":2,"y":3},"context":{"requestId":"invoke-1"}}')
echo "$RESP" | jq .
RESULT_SUM=$(echo "$RESP" | jq -r '.result.product')
RESULT_MSG=$(echo "$RESP" | jq -r '.result.message')
[[ "$RESULT_SUM" == "6" ]] || fail "Invocation returned unexpected product: $RESULT_SUM"
pass "Function 1 invoked successfully"

echo "Deploying already-deployed function again with no changes (should fail 409)..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  "$BASE_URL/functions/$FN_ID_1/deploy" \
  -H "Authorization: Bearer $TOKEN")
assert_status "Re-deploy with no changes returns 409" 409 "$STATUS"

echo "Uploading new artifact to re-enable deploy..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  "$BASE_URL/functions/$FN_ID_1/artifacts" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$PY_FILE;type=text/x-python")
assert_status "Re-upload new artifact" 200 "$STATUS"

echo "Re-deploying function 1 after new artifact..."
RESP=$(curl -s -X POST "$BASE_URL/functions/$FN_ID_1/deploy" \
  -H "Authorization: Bearer $TOKEN")
echo "$RESP" | jq .
[[ "$(echo "$RESP" | jq -r '.status')" == "DEPLOYED" ]] || fail "Re-deploy failed"
pass "Function 1 re-deployed successfully"

# ─────────────────────────────────────────────
section "9. AUTH — Isolation between users"
# ─────────────────────────────────────────────

echo "Logging in as user 2..."
TOKEN_2=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL_2\",\"password\":\"$PASSWORD\"}" | jq -r '.accessToken')
[[ -n "$TOKEN_2" && "$TOKEN_2" != "null" ]] || fail "User 2 login failed"
pass "User 2 logged in"

echo "User 2 trying to get user 1's function (should fail 404)..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  "$BASE_URL/functions/$FN_ID_1" \
  -H "Authorization: Bearer $TOKEN_2")
assert_status "Cross-user access blocked" 404 "$STATUS"

echo "User 2 trying to delete user 1's function (should fail 404)..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
  "$BASE_URL/functions/$FN_ID_1" \
  -H "Authorization: Bearer $TOKEN_2")
assert_status "Cross-user delete blocked" 404 "$STATUS"

echo "User 2 lists their own functions (should be empty)..."
RESP=$(curl -s "$BASE_URL/functions" -H "Authorization: Bearer $TOKEN_2")
COUNT=$(echo "$RESP" | jq '.totalElements')
[[ "$COUNT" -eq 0 ]] || fail "User 2 should see 0 functions, saw $COUNT"
pass "User isolation confirmed — user 2 sees $COUNT functions"

# ─────────────────────────────────────────────
section "10. AUTH — Refresh token"
# ─────────────────────────────────────────────

echo "Refreshing user 1 token..."
RESP=$(curl -s -X POST "$BASE_URL/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refreshToken\":\"$REFRESH_TOKEN\"}")
echo "$RESP" | jq .
NEW_TOKEN=$(echo "$RESP" | jq -r '.accessToken')
[[ -n "$NEW_TOKEN" && "$NEW_TOKEN" != "null" ]] || fail "Token refresh failed"
pass "Token refreshed"
TOKEN="$NEW_TOKEN"

echo "Using invalid refresh token (should fail 401)..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{"refreshToken":"00000000-0000-0000-0000-000000000000"}')
assert_status "Invalid refresh token rejected" 401 "$STATUS"

# ─────────────────────────────────────────────
section "11. DELETE — Delete functions"
# ─────────────────────────────────────────────

echo "Deleting function 3..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
  "$BASE_URL/functions/$FN_ID_3" \
  -H "Authorization: Bearer $TOKEN")
assert_status "Function 3 deleted" 204 "$STATUS"

echo "Function 3 should now be gone (404)..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  "$BASE_URL/functions/$FN_ID_3" \
  -H "Authorization: Bearer $TOKEN")
assert_status "Deleted function returns 404" 404 "$STATUS"

echo "Deleting function 3 again (should fail 404)..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
  "$BASE_URL/functions/$FN_ID_3" \
  -H "Authorization: Bearer $TOKEN")
assert_status "Double-delete returns 404" 404 "$STATUS"

echo "Deleting function 2 (no artifact, never deployed)..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
  "$BASE_URL/functions/$FN_ID_2" \
  -H "Authorization: Bearer $TOKEN")
assert_status "Function 2 deleted" 204 "$STATUS"

echo "Listing remaining functions (should be 1)..."
RESP=$(curl -s "$BASE_URL/functions" -H "Authorization: Bearer $TOKEN")
echo "$RESP" | jq '{totalElements, content: [.content[] | {id, name, deploymentStatus}]}'
REMAINING=$(echo "$RESP" | jq '.totalElements')
[[ "$REMAINING" -eq 1 ]] || fail "Expected 1 remaining function, got $REMAINING"
pass "1 function remains"

# ─────────────────────────────────────────────
section "12. AUTH — Logout"
# ─────────────────────────────────────────────

echo "Logging out user 1..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/auth/logout" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"refreshToken\":\"$(curl -s -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL_1\",\"password\":\"$PASSWORD\"}" | jq -r '.refreshToken')\"}")
assert_status "Logout" 200 "$STATUS"
pass "User 1 logged out"

# ─────────────────────────────────────────────
echo -e "\n${GREEN}══════════════════════════════════${NC}"
echo -e "${GREEN}  All tests passed! ✓${NC}"
echo -e "${GREEN}══════════════════════════════════${NC}"
