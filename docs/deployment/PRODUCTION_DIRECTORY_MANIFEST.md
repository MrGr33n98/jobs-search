# Production Directory Manifest — Target Path `/opt/job-search`

| Path | Owner:Group | Permissions | Purpose | Persistent? | Backup? | Contains PII? |
|------|-------------|-------------|---------|-------------|---------|---------------|
| `/opt/job-search/` | `openings:openings` (1000:1000) | `0755` | Base deployment root | YES | NO | NO |
| `/opt/job-search/app/` | `openings:openings` (1000:1000) | `0755` | Cloned repository / release files | NO (Ephemeral) | NO | NO |
| `/opt/job-search/config/` | `openings:openings` (1000:1000) | `0755` | Candidate profile & company configs | YES | YES | YES |
| `/opt/job-search/data/` | `openings:openings` (1000:1000) | `0755` | Docker volume mount (`job-search-data`) | YES | YES | YES |
| `/opt/job-search/logs/` | `openings:openings` (1000:1000) | `0755` | Rotating container stdout/stderr logs | YES | NO | NO |
| `/opt/job-search/backups/` | `openings:openings` (1000:1000) | `0700` | Automated database backup tarballs | YES | YES | YES |
| `/opt/job-search/deploy/` | `openings:openings` (1000:1000) | `0755` | Compose, Dockerfiles, deploy scripts | YES | YES | NO |
| `/opt/job-search/.env` | `openings:openings` (1000:1000) | `0600` | Production environment secrets | YES | YES | YES |
