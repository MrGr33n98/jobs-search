#!/usr/bin/env bash
# =============================================================================
# Release-Based Production Deployment Script — Personal Job Search OS
# =============================================================================
# NOTE: DO NOT EXECUTE ON PRODUCTION VM WITHOUT APPROVAL IN SEPARATE WAVE.
# =============================================================================
set -Eeuo pipefail

DEPLOY_ROOT="/opt/job-search"
COMPOSE_FILE="deploy/docker-compose.production.yml"

echo "==> Initiating Job Search OS Production Deployment..."

# 1. Run Pre-flight Checks
./deploy/scripts/predeploy-check.sh "$COMPOSE_FILE" "settings.yaml"

# 2. Trigger automatic backup before release if stack is running
if docker compose -f "$COMPOSE_FILE" ps --quiet | grep -q .; then
    echo "--> Existing release detected. Triggering automated backup..."
    ./deploy/scripts/backup.sh "${DEPLOY_ROOT}/backups"
fi

# 3. Pull / Build latest production images
echo "--> Building production image..."
docker compose -f "$COMPOSE_FILE" build --no-cache

# 4. Launch project containers with zero downtime
echo "--> Launching production containers..."
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

# 5. Run Post-deployment Smoke Tests
echo "--> Executing Post-deployment Smoke Tests..."
./deploy/scripts/smoke-test.sh

echo "==> Deployment Completed Successfully."
