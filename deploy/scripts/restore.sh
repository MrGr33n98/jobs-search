#!/usr/bin/env bash
# =============================================================================
# Guarded Database & Volume Restore Script — Personal Job Search OS
# =============================================================================
set -Eeuo pipefail

BACKUP_FILE="${1:-}"

if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Usage: $0 /path/to/openings_backup_YYYYMMDD_HHMMSS.tar.gz"
    exit 1
fi

echo "=================================================================="
echo "WARNING: RESTORE PROCEDURE"
echo "Target Backup: $BACKUP_FILE"
echo "This operation will overwrite data in 'job-search-data' volume."
echo "=================================================================="

read -p "Type 'RESTORE' to proceed with data restoration: " CONFIRMATION
if [ "$CONFIRMATION" != "RESTORE" ]; then
    echo "Restoration cancelled by user."
    exit 0
fi

echo "--> Verifying checksum if available..."
if [ -f "${BACKUP_FILE}.sha256" ]; then
    sha256sum -c "${BACKUP_FILE}.sha256"
fi

echo "--> Stopping running job-search containers..."
docker compose -f deploy/docker-compose.production.yml stop || true

BACKUP_DIR=$(dirname "$BACKUP_FILE")
BACKUP_NAME=$(basename "$BACKUP_FILE")

echo "--> Extracting backup archive into 'job-search-data' volume..."
docker run --rm \
  -v job-search-data:/data \
  -v "$BACKUP_DIR":/backup \
  alpine sh -c "rm -rf /data/* && tar -xzf /backup/$BACKUP_NAME -C /data"

echo "--> Restarting job-search containers..."
docker compose -f deploy/docker-compose.production.yml start

echo "==> Data Restoration Completed Successfully."
