# GitHub Secrets & Environment Configuration — Personal Job Search OS

## Overview

The CD pipeline uses GitHub Actions Environments and Secrets to deploy safely to the production VM without exposing secrets in source code or logs.

---

## Required GitHub Environment & Secrets

### Environment Setup
- **Environment Name:** `production`
- **Protection Rules:** Enable **Required reviewers** (select your GitHub user) to enforce manual approval before deployment execution.

---

### Required Secrets

Configure these secrets in **Repository Settings -> Environments -> production -> Environment secrets**:

| Secret Name | Description | Example Value |
| :--- | :--- | :--- |
| `PRODUCTION_HOST` | IPv4 address of the production VM | `64.225.59.107` |
| `PRODUCTION_USER` | SSH deployment user | `root` |
| `PRODUCTION_SSH_KEY` | Private SSH key authorized on VM | `-----BEGIN OPENSSH PRIVATE KEY-----...` |

---

## Secrets Safety Policy

1. **`OPENINGS_API_TOKEN` MUST NOT be stored in GitHub Secrets.**
   - Production secrets and tokens reside exclusively at `/opt/job-search/.env` on target VM `64.225.59.107`.
   - The CD pipeline preserves `/opt/job-search/.env` during deployments and never overwrites it.
2. **`GITHUB_TOKEN` is automatically scoped.**
   - CI/CD uses `${{ secrets.GITHUB_TOKEN }}` to authenticate to GHCR (`ghcr.io`).
3. **Zero Secret Exposure.**
   - Secrets are masked automatically by GitHub Actions runners.
   - Logs, reports, artifacts, and screenshots must never print private keys or tokens.
