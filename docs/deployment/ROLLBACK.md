# Production Rollback & Emergency Recovery — Personal Job Search OS

## Overview

Rollback mechanisms are designed to safely revert application code without risking data loss or damaging persistent volumes (`job-search-data`).

---

## 1. Automatic Application Rollback (CD Pipeline)

If any of the following occur during CD deployment:
- `job-search-web` fails to start
- Healthcheck times out (120 seconds)
- SQLite `PRAGMA integrity_check` fails
- Post-deploy job count drops below pre-deploy baseline
- REST / MCP smoke tests fail

The CD script **automatically reverts** the image tag in `docker-compose.production.yml` to the previous image and restarts `job-search-web`.

---

## 2. Manual Application Rollback (CLI / SSH)

To manually roll back `job-search-web` to a previous release tag:

```bash
ssh root@64.225.59.107
cd /opt/job-search

# Inspect available release metadata
ls -la releases/

# Edit image reference in docker-compose.production.yml to target previous commit SHA tag
sed -i "s|image: .*|image: ghcr.io/<owner>/openings:<PREVIOUS_SHA>|g" docker-compose.production.yml

# Recreate web container
docker compose -f docker-compose.production.yml up -d web
```

---

## 3. Emergency Data Restoration

> [!CAUTION]
> **DATABASE RESTORATION OVERWRITES RECENT DATA**
> 
> Only restore data if database corruption or catastrophic data loss has occurred.

To restore from a pre-deploy backup:

```bash
ssh root@64.225.59.107
cd /opt/job-search

# 1. Verify backup SHA256 checksum
cd backups/
sha256sum -c job-search-predeploy-<TIMESTAMP>-<SHA>.tar.gz.sha256

# 2. Stop running web container
cd /opt/job-search
docker compose -f docker-compose.production.yml stop web

# 3. Extract backup into job-search-data volume
docker run --rm \
  -v job-search-data:/data \
  -v /opt/job-search/backups:/backup \
  alpine sh -c "rm -rf /data/* && tar -xzf /backup/job-search-predeploy-<TIMESTAMP>-<SHA>.tar.gz -C /data && chown -R 1000:1000 /data"

# 4. Restart web container
docker compose -f docker-compose.production.yml up -d web

# 5. Verify integrity
docker exec job-search-web openings healthcheck
```

---

## 4. Volume Safety Rules

- **NEVER** run `docker compose down -v`.
- **NEVER** run `docker volume rm job-search-data`.
- **NEVER** run `docker system prune` or `docker volume prune` on production VM.
