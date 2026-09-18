# Local Setup & Operations Quickstart — Openings OS

**Target Directory:** `/home/felipe/Desktop/curriculo-2026/job-apply/openings`

## Commands Reference:

### Start Operations
```bash
docker compose up -d
```

### Stop Operations
```bash
docker compose down
```

### Restart Operations
```bash
docker compose restart
```

### View Logs
```bash
docker compose logs -f web
```

### Healthcheck
```bash
docker compose exec web openings healthcheck
```

### Rescore Postings
```bash
docker compose exec web openings rescore
```

### Run Job Collection Now
```bash
docker compose exec web openings run
```

### Backup Database & Config
```bash
docker compose exec web tar -czf /tmp/openings-backup.tar.gz /data
```

### Access Dashboard & MCP Endpoint
- **Web Dashboard:** `http://127.0.0.1:8501`
- **MCP Endpoint:** `http://127.0.0.1:8501/mcp`
