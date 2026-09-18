# Operations Runbook — Openings Personal Job Search OS

## 1. Daily Routine
1. Access `http://127.0.0.1:8501` to view new ingested postings.
2. Review top-scored jobs (score >= 30).
3. Move unwanted/irrelevant jobs to `Blacklist` or `Rejected`.
4. Move strong matches to `Shortlisted`.

## 2. Application Packaging Workflow
1. For shortlisted jobs, run agent skill to generate tailored CV and cover letter.
2. Store assets as attachments via MCP or Web interface.
3. Review `config/profile_review_required.yaml` for unconfirmed facts.
4. Manually submit on careers portal and set status to `Applied`.

## 3. Maintenance & Backup
- Daily automatic volume persistence via Docker named volume `openings-data`.
- Run `openings healthcheck` weekly.
