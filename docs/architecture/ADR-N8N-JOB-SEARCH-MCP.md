# ADR 001: Architecture & Responsibility Model for n8n and Job Search MCP

**Status:** Accepted  
**Date:** 2026-09-18  

## Context
The system consists of two primary operational domains:
1. **Job Search OS (`openings`):** Domain Owner for candidate data, job postings, deduplication, canonical scoring engine, and human-in-the-loop (HITL) application state.
2. **n8n Automation Engine:** Orchestration Owner for cron schedules, daily digests, Telegram/Slack notifications, and multi-step approval workflows.

## Decisions

### 1. Existing n8n MCP Server Preservation
The n8n MCP server endpoint (`https://n8n.avaliasolar.com.br/mcp-server/http`) is ALREADY OPERATIONAL and tested using `supergateway`. It will not be replaced, modified, or re-created.

### 2. Business Logic Centralization (Zero Duplication)
Canonical scoring and candidate fit algorithms belong **exclusively** to Job Search OS. n8n workflows MUST NOT calculate their own scoring rules in JavaScript nodes; instead, n8n queries Job Search API/MCP and consumes the canonical score.

### 3. Private Communication on Production VM
Upon deployment to VM `64.225.59.107`, n8n and Job Search OS communicate over internal localhost/host-gateway or private Docker bridge network. Job Search OS `/mcp` is not exposed to the public internet.

### 4. Human-In-The-Loop Boundary
Submitting job applications, accepting legal terms, or sending external emails is strictly forbidden for automated agents. Workflows in n8n stop at candidate notification and draft preparation.
