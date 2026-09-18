# Deployment Test Matrix — Wave DEPLOY-01

| ID | Layer | Scenario | Expected Result | Local Evidence / Status |
|----|-------|----------|-----------------|-------------------------|
| `TEST-01` | APP | Healthcheck Command | `OK` across imports, config, DB, dirs | **PASS** (`docker compose exec web openings healthcheck`) |
| `TEST-02` | API | `GET /api/dashboard/auth` | `{"token_required": false}` | **PASS** (HTTP 200) |
| `TEST-03` | API | `GET /api/jobs` | JSON array of postings with metrics | **PASS** (126 jobs returned) |
| `TEST-04` | MCP | MCP Tool Discovery | 27 tools mapped and listed | **PASS** (`docs/MCP_TOOL_INVENTORY.md`) |
| `TEST-05` | DB | SQLite Concurrency & Pragmas | `foreign_keys=ON`, `busy_timeout=5000` | **PASS** (`src/openings/db/base.py`) |
| `TEST-06` | DOCKER | Compose Production Syntax | Valid compose config | **PASS** (`docker compose -f deploy/docker-compose.production.yml config`) |
| `TEST-07` | SCRIPTS | Pre-flight Check Syntax | Executable with `0` syntax errors | **PASS** (`bash -n deploy/scripts/*.sh`) |
| `TEST-08` | HITL | Submission Protection | No auto-submit capability | **PASS** (Zero auto-apply code) |
| `TEST-09` | SECURITY | Secret Sanitization | `$ENV_VAR` indirection, zero hardcoded keys | **PASS** (`src/openings/config.py`) |
| `TEST-10` | PERSISTENCE | Container Restart Persistence | Volume data preserved across restarts | **PASS** (Tested with `openings rescore`) |
