# CI/CD Architecture & Pipeline Documentation — Personal Job Search OS

## Overview

The Personal Job Search OS (`openings`) uses a two-stage, safe, minimal CI/CD pipeline built on **GitHub Actions**:

```
Developer / Feature Branch
           │
           ▼
     Pull Request ──────────► Automatic CI (.github/workflows/ci.yml)
           │                   ├── Lint & Static Analysis (mypy, pre-commit)
           │                   ├── Python Unit & Integration Tests (pytest)
           │                   ├── Frontend Build & Quality Gate (npm)
           │                   ├── Playwright End-to-End Suite
           │                   ├── Dependency Security Audit (pip-audit)
           │                   └── Docker Build & Compose Topology Validation
           ▼
     Merge to main ─────────► Automatic CI & Image Build to GHCR
           │
           ▼
   Production Deploy ───────► Manual Approval (workflow_dispatch)
                               └── Controlled CD (.github/workflows/deploy-production.yml)
```

---

## 1. Continuous Integration (CI)

- **Workflow:** `.github/workflows/ci.yml`
- **Triggers:** Pull Requests and pushes to `main`.
- **Isolation:** CI runs in isolated GitHub-hosted runners without access to production credentials, SSH keys, or production data.
- **Jobs Executed:**
  1. `quality`: Pre-commit linters and Mypy static type checking.
  2. `test`: Pytest unit and integration test suite across Python 3.12 and 3.13.
  3. `frontend`: Node.js 22 build, lint, and component quality gate.
  4. `e2e`: Playwright dashboard UI tests against mock backend.
  5. `security`: `pip-audit` for dependency vulnerabilities and repository security rules (no `0.0.0.0:8501` bindings, no committed `.env` or SSH keys).
  6. `docker`: Docker image build validation, health check test, and compose topology checks.

---

## 2. Continuous Deployment (CD)

- **Workflow:** `.github/workflows/deploy-production.yml`
- **Trigger:** Manual trigger via `workflow_dispatch` (with GitHub Environment `production` protection).
- **Concurrency Guard:** `group: job-search-production` with `cancel-in-progress: false` to prevent overlapping deployments.
- **Image Tagging:** Immutable Git SHA tags (`ghcr.io/<owner>/openings:<git-sha>`). `latest` tag is updated simultaneously.
- **Production Guarantees:**
  - Mandatory pre-deploy database tarball backup with SHA256 verification.
  - Recreates `web` container ONLY. `scheduler` remains **STOPPED**.
  - Enforces SQLite `PRAGMA integrity_check => ok` and non-decreasing job count invariants.
  - Automatic rollback on container health timeout or smoke test failure.

---

## 3. Daily Developer Workflow

1. Create a feature branch off `main`.
2. Commit changes and push to GitHub.
3. Open a Pull Request. CI executes automatically.
4. Merge PR to `main` upon CI pass.
5. Trigger manual production deployment from GitHub Actions UI when ready.
