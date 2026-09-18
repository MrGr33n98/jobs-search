# Deployment Runbook — Wave DEPLOY-02 (Future VM Execution)

**Target Host:** `64.225.59.107` (Ubuntu 24.04 LTS)  
**Target Root:** `/opt/job-search`  

---

## 1. Execution Checklist for Deployment Wave

```bash
# 1. Access Production VM
ssh root@64.225.59.107

# 2. Execute Pre-flight Inspection
uname -a && free -h && df -h /opt
ss -lntp | grep :8501

# 3. Create Target Root
mkdir -p /opt/job-search
cd /opt/job-search

# 4. Clone / Sync Production Release Package
git clone https://github.com/VincenzoImp/openings.git app
cp app/deploy/docker-compose.production.yml docker-compose.production.yml
cp app/deploy/.env.production.example .env

# 5. Execute Pre-deploy Check Script
bash app/deploy/scripts/predeploy-check.sh docker-compose.production.yml app/settings.yaml

# 6. Launch Production Stack
docker compose -f docker-compose.production.yml up -d

# 7. Execute Post-deploy Smoke Tests
bash app/deploy/scripts/smoke-test.sh
```
