#!/usr/bin/env bash
# =============================================================================
# Pre-deployment Pre-flight Check Script — Personal Job Search OS
# =============================================================================
set -Eeuo pipefail

echo "==> Running Pre-deployment Pre-flight Checks..."

# 1. Check Docker & Docker Compose availability
if ! command -v docker &> /dev/null; then
    echo "ERROR: 'docker' CLI is not installed or not in PATH."
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "ERROR: 'docker compose' plugin is not available."
    exit 1
fi

# 2. Validate Compose file syntax
COMPOSE_FILE="${1:-deploy/docker-compose.production.yml}"
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "ERROR: Compose file '$COMPOSE_FILE' not found."
    exit 1
fi

echo "--> Validating Compose syntax for '$COMPOSE_FILE'..."
docker compose -f "$COMPOSE_FILE" config --quiet
echo "--> Compose syntax OK."

# 3. Check port 8501 availability
echo "--> Checking if port 8501 is available on 127.0.0.1..."
if command -v ss &> /dev/null; then
    if ss -lntp | grep -q ":8501 "; then
        echo "WARNING: Port 8501 is currently in use."
    else
        echo "--> Port 8501 is free."
    fi
fi

# 4. Check settings.yaml existence
SETTINGS_FILE="${2:-settings.yaml}"
if [ ! -f "$SETTINGS_FILE" ]; then
    echo "ERROR: '$SETTINGS_FILE' not found."
    exit 1
fi
echo "--> settings.yaml found."

# 5. Check candidate profile existence
PROFILE_FILE="config/candidate_profile.yaml"
if [ ! -f "$PROFILE_FILE" ]; then
    echo "ERROR: '$PROFILE_FILE' not found."
    exit 1
fi
echo "--> candidate_profile.yaml found."

echo "==> All Pre-flight Checks PASSED."
