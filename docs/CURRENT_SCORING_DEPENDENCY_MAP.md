# Current scoring dependency map

| Component | Reads `jobs.relevance_score` | Writes `jobs.relevance_score` | Threshold dependency | Compatibility strategy |
| --- | --- | --- | --- | --- |
| `openings.scoring.calculate_relevance_score` | No | No | No | Preserve as the legacy YAML scorer. |
| `openings.scoring.score_jobs` | No | DataFrame only | No | Preserve for legacy collection and tests. |
| `openings.pipeline.run_collection` | No | Via `upsert_jobs` after legacy scoring | `save_threshold`, `notify_threshold` | Keep the YAML path unchanged. |
| `db.upsert_jobs` | Existing row value | Yes, for legacy collection | No | Profile runs use `save_threshold=0`; profile score is never copied here. |
| Inbox/job queries | Yes | No | `min_score`/`max_score` | Remain legacy until CAREER-01F. |
| Pipeline view | Yes | No | No | Remain legacy until CAREER-01F. |
| notifier | Yes | No | `notify_threshold` | Remain legacy-only. |
| exports, stats and bundles | Yes | No | Some stats/filter paths | Preserve existing contracts. |
| scheduler and legacy run-now | Yes indirectly | Legacy path only | Legacy thresholds | Not changed or started. |
| `job_matches` query | No | No | No | Sorts by profile-specific `job_matches.relevance_score`. |

## CAREER-01E boundary

`Job.relevance_score` remains a compatibility field for the legacy YAML path.
The new deterministic scorer writes only the `(job_id, search_profile_id)`
relationship through `JobMatch`. No profile score is copied back to `jobs`.
