# Rollback Runbook — Production Emergency Recovery

## 1. Safety Directives
- **NEVER execute `docker compose down -v`.** Volume deletion destroys database and attachments.
- Rollback restores previous container images while preserving volume `job-search-data`.

## 2. Emergency Rollback Execution

```bash
# 1. Access Deployment Root
cd /opt/job-search

# 2. Trigger Automated Rollback Script
bash app/deploy/scripts/rollback.sh docker-compose.production.yml

# 3. Verify Health Post-Rollback
docker compose -f docker-compose.production.yml ps
bash app/deploy/scripts/smoke-test.sh
```
