# Production Architecture — Personal Job Search OS

## 1. Container Topology

```mermaid
graph TD
    subgraph "Target Host: 64.225.59.107 (/opt/job-search)"
        subgraph "Docker Project: job-search"
            WEB[job-search-web <br/> 127.0.0.1:8501]
            SCHED[job-search-scheduler]
            VOL[(job-search-data <br/> Volume)]
            NET[job-search-internal <br/> Bridge Network]
        end
    end

    WEB <--> VOL
    SCHED <--> VOL
    WEB --- NET
    SCHED --- NET
```

## 2. Structural Guarantees
- **Web Service:** `job-search-web` exposes REST API and MCP endpoint locally on `127.0.0.1:8501`.
- **Scheduler Service:** `job-search-scheduler` runs single-instance intake and rescoring loop at configured 12h interval.
- **Persistence Layer:** SQLite database and generated attachments stored in named volume `job-search-data` mounted at `/data`.
