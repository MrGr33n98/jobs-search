# VM Pre-Flight Inspection Runbook — Read-Only Commands

**Target Host:** `64.225.59.107` (Ubuntu 24.04 LTS)
**Execution Phase:** Future Deployment Wave Pre-Flight Audit

```bash
# System Resources
uname -a
uptime
free -h
df -h /opt

# Active Docker Workloads Audit (Non-destructive)
docker ps
docker stats --no-stream
docker network ls
docker volume ls

# Port Collision Inspection
ss -lntp | grep :8501

# Storage Health Audit
docker system df
```

## Safety Checklist:
- [ ] Port `8501` is free on `127.0.0.1`.
- [ ] Directory `/opt/job-search` exists or can be created with permissions `0755`.
- [ ] At least 5 GB disk space available under `/opt`.
- [ ] Docker engine and `docker compose` plugin are active.
