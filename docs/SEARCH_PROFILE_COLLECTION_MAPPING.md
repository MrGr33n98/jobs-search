# SearchProfile collection mapping

CAREER-01D keeps the legacy YAML path intact. A profile run deep-copies the
loaded global `Config`, applies only strategy fields to that copy, and passes
the copy through the existing `collect_all()` orchestration and adapters.

| SearchProfile field | Consumer | Transformation | Legacy fallback | Risk |
| --- | --- | --- | --- | --- |
| `target_roles`, `role_aliases` | JobSpy queries; ATS/RSS title filters | Separate deterministic query terms; title patterns for configured company/feed adapters | Existing titles when profile roles are empty | Adapter semantics can vary |
| `include_keywords` | JobSpy queries; ATS/RSS title filters | Additional deterministic terms | None | Different adapters interpret terms differently |
| `exclude_keywords` | Profile post-collection filter | Case-insensitive title/company/location/description filter | None | Exclusion is not native in every adapter |
| `locations`, `countries` | JobSpy, JobCloud, Adzuna, company/feed filters | Deduplicated strings; countries also select JobSpy country | Legacy JobSpy locations | Unknown posting location is retained |
| `location_types`, remote fields | Plan metadata only in 01D | No unsupported adapter argument is invented | None | Full eligibility belongs to 01E scoring |
| `employment_types` | JobSpy and configured strategy adapters | Profile values or legacy JobSpy values | Legacy JobSpy job types | Vocabulary is normalized downstream |
| `sources` | `collect_all()` effective config | Capabilities + enabled adapter intersection | None | Disabled/missing source is a controlled plan error |
| `freshness_days` | JobSpy `hours_old`; company max age | Days converted to hours for JobSpy | Legacy age settings | Source precision differs |

Operational settings remain global and server-side: retry, throttling,
parallelism, proxies, timeouts, secrets, paths, and user-agent settings.
The copied config sets `save_threshold=0` only for profile collection so the
canonical Job Pool is not filtered before CAREER-01E can create matches. The
legacy `jobs.relevance_score` column remains untouched by this boundary.

Invalid JobSpy countries use the safe `worldwide` fallback with an explicit
run warning. Workday and other company adapter failures remain isolated in
their existing per-company `SourceRunStats` boundary.
