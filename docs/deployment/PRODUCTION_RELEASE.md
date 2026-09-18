# Production Release Manual & Runbook — Personal Job Search OS

## Standard Production Release Procedure

### 1. Pre-Deployment Verification

Before triggering a production release:
1. Ensure `.github/workflows/ci.yml` has passed green for the target commit on `main`.
2. Confirm target VM `64.225.59.107` has at least 5 GB free disk space.
3. Confirm existing production services (Avalia, n8n, Fleetlex, NPM) are healthy.

---

### 2. Executing the Release via GitHub Actions

1. Go to the GitHub Repository **Actions** tab.
2. Select **CD Production Deployment**.
3. Click **Run workflow**.
4. (Optional) Provide a specific Commit SHA or leave blank to deploy HEAD of `main`.
5. Click **Run workflow**.

---

### 3. Automated CD Steps Executed on Target Host

```
1. Pre-deploy checks (Disk space > 5GB, docker/compose status, pre-deploy jobs count)
2. Pre-deploy database backup tarball + SHA256 verification
3. Docker image pull from GHCR (ghcr.io/<owner>/openings:<git-sha>)
4. Write release metadata (/opt/job-search/releases/<sha>/release.json)
5. Recreate web container only (docker compose up -d web)
6. Bounded healthcheck wait loop (max 120 seconds)
7. SQLite integrity check (PRAGMA integrity_check => ok) & job count invariant
8. Post-deploy REST & MCP smoke tests (http://127.0.0.1:8501/health & https://jobs.avaliasolar.com.br/health)
9. Verify scheduler remains STOPPED & port 8501 remains bound to 127.0.0.1
```

---

### 4. Release Metadata Format

Each release generates an immutable audit record at `/opt/job-search/releases/<sha>/release.json`:

```json
{
  "commit_sha": "a1b2c3d",
  "image": "ghcr.io/vincenzoimp/openings:a1b2c3d...",
  "deployed_at": "2026-09-18T20:00:00Z",
  "predeploy_jobs_count": 1010,
  "backup_path": "/opt/job-search/backups/job-search-predeploy-20260918_200000-a1b2c3d.tar.gz"
}
```

---

### 5. Post-Release Smoke Verification

Verify external endpoints after release:
- Dashboard: `https://jobs.avaliasolar.com.br`
- Health: `curl -fsS https://jobs.avaliasolar.com.br/health`
- Unauthenticated API protection: `curl -i https://jobs.avaliasolar.com.br/api/jobs` (Must return HTTP 401)
