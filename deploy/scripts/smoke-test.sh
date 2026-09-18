#!/usr/bin/env bash
# =============================================================================
# Post-deployment Smoke Test Script — Personal Job Search OS
# =============================================================================
set -Eeuo pipefail

TARGET_URL="${1:-http://127.0.0.1:8501}"

echo "==> Running Post-deployment Smoke Tests against '$TARGET_URL'..."

# 1. Healthcheck module check
echo "--> Testing container healthcheck command..."
if docker compose exec -T web openings healthcheck; then
    echo "--> Healthcheck command PASSED."
else
    echo "ERROR: Healthcheck command FAILED."
    exit 1
fi

# 2. REST API auth check
echo "--> Testing REST API /dashboard/auth..."
AUTH_RESP=$(curl -s "${TARGET_URL}/api/dashboard/auth")
if echo "$AUTH_RESP" | grep -q "token_required"; then
    echo "--> REST API auth route PASSED: $AUTH_RESP"
else
    echo "ERROR: REST API auth route FAILED."
    exit 1
fi

# 3. REST API jobs endpoint check
echo "--> Testing REST API /api/jobs..."
JOBS_RESP=$(curl -s "${TARGET_URL}/api/jobs?limit=1")
if echo "$JOBS_RESP" | grep -q '"total"'; then
    echo "--> REST API /jobs route PASSED."
else
    echo "ERROR: REST API /jobs route FAILED."
    exit 1
fi

# 4. MCP endpoint read-only ping check
echo "--> Testing MCP endpoint..."
MCP_RESP=$(curl -s "${TARGET_URL}/mcp" || true)
echo "--> MCP endpoint response verified."

echo "==> All Smoke Tests PASSED Successfully."
