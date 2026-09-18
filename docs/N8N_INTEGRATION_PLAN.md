# n8n Integration Plan — Phase 2

## Overview
Phase 2 describes optional automation workflows utilizing n8n without modifying existing n8n production instances in Phase 1.

## Workflows:
1. **`OPENINGS_DAILY_DIGEST`**:
   - Trigger: Daily Cron at 08:00 AM.
   - Action: Query Openings MCP (`list_jobs` with `statuses=["new"]`, `min_score=40`).
   - Output: Send summary digest to candidate via Telegram/Slack webhook.

2. **`INTERVIEW_PREP_TRIGGER`**:
   - Trigger: Openings Webhook or polling status change to `interviewing`.
   - Action: Call Interview Agent skill to generate interview briefing dossier.

3. **`APPLICATION_FOLLOWUP_REMINDER`**:
   - Trigger: 7 days after status updated to `applied`.
   - Action: Notify candidate to send a follow-up inquiry. (No automated email sent).
