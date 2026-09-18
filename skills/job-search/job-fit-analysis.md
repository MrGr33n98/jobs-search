# Skill: Job Fit Analysis

**Purpose:** Perform deterministic match scoring explanation and structured gap analysis for a target job posting.

## Rules:
1. Extract job requirements into:
   - `VERIFIED_MATCHES`: Skills/experience explicitly present in `candidate_profile.yaml`.
   - `PARTIAL_MATCHES`: Skills with adjacent evidence.
   - `GAPS`: Missing mandatory or optional requirements.
2. Produce score breakdown explaining points added and subtracted.
3. Output markdown report formatted for `applications/<job-id>/match-analysis.md`.
