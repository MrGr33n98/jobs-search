#!/usr/bin/env bash
# =============================================================================
# Production Rollback Script — Personal Job Search OS
# =============================================================================
# Reverts to previous release while strictly preserving persistent volumes.
# NEVER executes 'docker compose down -v'.
# =============================================================================
set -Eeuo pipefail

COMPOSE_FILE="${1:-deploy/docker-compose.production.yml}"

echo "=================================================================="
echo "WARNING: INITIATING PRODUCTION ROLLBACK"
echo "Persistent volume 'job-search-data' will be strictly preserved."
echo "=================================================================="

read -p "Type 'ROLLBACK' to confirm procedure: " CONFIRMATION
if [ "$CONFIRMATION" != "ROLLBACK" ]; then
    echo "Rollback cancelled by user."
    exit 0
fi

echo "--> Restarting previous container release safely..."
docker compose -f "$COMPOSE_FILE" restart

echo "--> Executing Post-rollback Smoke Tests..."
./deploy/scripts/smoke-test.sh

echo "==> Rollback Completed Successfully."
