#!/usr/bin/env bash
# =============================================================================
# Automated Backup Script — Personal Job Search OS
# =============================================================================
set -Eeuo pipefail

BACKUP_DIR="${1:-/opt/job-search/backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/openings_backup_${TIMESTAMP}.tar.gz"

mkdir -p "$BACKUP_DIR"

echo "==> Creating backup archive at '$BACKUP_FILE'..."

# Create tarball of database, attachments, logs, and config from volume or directory
if docker volume inspect job-search-data &>/dev/null; then
    docker run --rm \
      -v job-search-data:/data:ro \
      -v "$BACKUP_DIR":/backup \
      alpine tar -czf "/backup/openings_backup_${TIMESTAMP}.tar.gz" -C /data .

    echo "--> Computing sha256 checksum..."
    sha256sum "$BACKUP_FILE" > "${BACKUP_FILE}.sha256"
    echo "==> Backup completed successfully: ${BACKUP_FILE}"
else
    echo "ERROR: Docker volume 'job-search-data' not found."
    exit 1
fi
