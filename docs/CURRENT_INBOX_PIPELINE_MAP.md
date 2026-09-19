# Current Inbox / Pipeline map

| Component | Current data source | Current score | Current status | CAREER-01F strategy | Compatibility |
| --- | --- | --- | --- | --- | --- |
| Legacy Inbox | `GET /api/jobs` | `jobs.relevance_score` | `jobs.status` | Keep as explicit legacy view; add profile selector. | Existing filters, exports and shortcuts remain. |
| Profile Inbox | `GET /api/search-profiles/:id/matches` | `job_matches.relevance_score` (`score`) | `job_matches.review_status` | Profile URL context, server-side score/review filters. | Does not mix with legacy score. |
| Job detail | `GET /api/jobs/:id` | Legacy explanation | `jobs.status` | Original URL, notes, attachments preserved; profile match remains separate. | No destructive change. |
| Legacy Pipeline | `GET /api/jobs` with pipeline statuses | `jobs.relevance_score` | `jobs.status` | Retained as legacy job-status board. | Existing behavior remains. |
| Application Pipeline | `GET /api/applications` | Not used for stage | `applications.stage` | Explicit applications only, one per canonical Job. | Additive view. |
| Notes / attachments | Job detail APIs and local attachment store | Not applicable | Job-global | Reused unchanged. | Existing data preserved. |
| MCP mutations | Existing job status/material tools | Legacy score | Global Job status | No new external-application tool. | HITL boundary preserved. |

`Job`, `JobMatch`, and `Application` remain distinct. A collection or score
never creates an Application; only the explicit add-to-pipeline action does.
