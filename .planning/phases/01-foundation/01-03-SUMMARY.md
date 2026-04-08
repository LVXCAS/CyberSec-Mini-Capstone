# Phase 01 Plan 03: Orchestrator with Safety Filter, SSH Execution, and SQLite Logging

**One-liner:** FastAPI orchestrator with blocklist safety filter, Paramiko SSH to battleground, and WAL-mode SQLite logging all agent actions.

**Completed:** 2026-04-08
**Duration:** ~10 minutes
**Tasks:** 2/2

---

## What Was Built

### Safety Filter (`orchestrator/safety_filter.py`)
- Blocklist-based validation using regex patterns
- 12 dangerous command patterns blocked (rm -rf /, mkfs, dd, shutdown, fork bombs, etc.)
- Role-based restrictions: blue cannot run nmap/metasploit/hydra; red cannot run auditd/iptables/ufw/fail2ban
- Returns structured FilterResult with blocked reason visible for demo

### SSH Executor (`orchestrator/ssh_executor.py`)
- Paramiko SSH client connecting to battleground container
- Configurable timeout (default 30s) with graceful timeout handling
- Output truncation at 4096 chars to prevent context explosion
- Graceful connection error handling

### SQLite Database (`orchestrator/db.py`)
- Three tables: decision_log, safety_log, findings
- WAL mode for concurrent reads
- Functions: init_db, log_decision, log_safety_check, log_finding, get_recent_decisions

### FastAPI App (`orchestrator/main.py`)
- `GET /health` - health check
- `POST /execute` - safety filter -> SSH execute -> log to SQLite
- `GET /decisions/{agent_role}` - retrieve recent decisions for context building
- `POST /findings` - log agent discoveries
- Startup: initializes DB, probes SSH connection

### Infrastructure Updates
- `orchestrator/Dockerfile` updated for package-based imports
- `docker-compose.yml` adds orchestrator-data volume and BATTLEGROUND_PASSWORD env var
- `orchestrator/__init__.py` added for Python package structure

---

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 5141185 | Safety filter, SSH executor, SQLite database, requirements |
| 2 | 949ee32 | FastAPI orchestrator with all endpoints |

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Wrong battleground SSH password**
- **Found during:** Task 2 verification
- **Issue:** Plan specified password "SecureAdmin1" but battleground setup.sh sets "Pr0jectAdmin1"
- **Fix:** Updated default in ssh_executor.py and docker-compose.yml environment variable
- **Files modified:** orchestrator/ssh_executor.py, docker-compose.yml

**2. [Rule 3 - Blocking] Dockerfile needed package structure**
- **Found during:** Task 2
- **Issue:** Imports use `from orchestrator.db import ...` requiring package layout in container
- **Fix:** Updated Dockerfile to copy into /app/orchestrator/ and run uvicorn with orchestrator.main:app
- **Files modified:** orchestrator/Dockerfile, orchestrator/__init__.py (new)

**3. [Rule 2 - Missing Critical] SQLite volume persistence**
- **Found during:** Task 2
- **Issue:** No volume mount for /app/data meant SQLite would be lost on container restart
- **Fix:** Added orchestrator-data named volume in docker-compose.yml
- **Files modified:** docker-compose.yml

---

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Blocklist approach (not allowlist) | Demo needs visible blocked commands; allowlist too restrictive for exploratory agents |
| 4096 char output truncation | Prevents LLM context explosion from large command outputs |
| WAL mode SQLite | Allows concurrent reads from multiple agents without blocking |

---

## Verification Results

- Safety filter rejects `rm -rf /` with clear reason
- Safety filter allows `nmap` for red agent
- SSH executor successfully runs `whoami` on battleground (returns "admin")
- Blocked commands return structured response with reason for demo visibility
- Decisions endpoint returns logged entries
- Health endpoint returns ok
