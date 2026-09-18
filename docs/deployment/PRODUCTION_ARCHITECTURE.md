# Production Architecture — Personal Job Search OS

## 1. Container Topology

```mermaid
graph TD
    subgraph "Target Host: 64.225.59.107 (/opt/job-search)"
        subgraph "Docker Project: job-search"
            WEB[web service <br/> 127.0.0.1:8501]
            SCHED[job-search-scheduler]
            VOL[(job-search-data <br/> Volume)]
        end
    end

    WEB <--> VOL
    SCHED <--> VOL
    INTERNET -->|Port 443| NPM
    NPM -->|job-search-internal| WEB
```

## Service Topology

- **Web Service:** Exposes REST API and MCP endpoint locally on `127.0.0.1:8501`.
- **Scheduler Service:** `job-search-scheduler` runs single-instance intake and rescoring loop at configured 12h interval.
- **Persistence Layer:** SQLite database and generated attachments stored in named volume `job-search-data` mounted at `/data`.
