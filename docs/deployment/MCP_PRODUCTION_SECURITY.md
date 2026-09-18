# MCP Production Security Model

## 1. Network & Protocol Isolation
- **Local Endpoint:** `http://127.0.0.1:8501/mcp` (Streamable HTTP).
- **Public Exposure:** Disabled by default (`OPENINGS_WEB_BIND=127.0.0.1`).
- **Token Protection:** Optional token-gating enabled via `OPENINGS_API_TOKEN` environment variable.

## 2. Mutation & HITL Guardrails
- **Read-Only Tools:** `list_jobs`, `get_job`, `search_similar`, `get_statistics`, `get_facets`, `get_settings` have zero side-effects.
- **Write Tools:** `add_job`, `add_note`, `add_attachment`, `set_status` mutate state inside the local SQLite database.
- **Forbidden Actions:** No MCP tool exists or is permitted to perform external job application submission, email sending, or legal form agreement.
