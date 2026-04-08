---
phase: 01-foundation
plan: 01
subsystem: infrastructure
tags: [docker, networking, containers, ssh, mysql, apache, php]

dependency-graph:
  requires: []
  provides: [docker-compose, container-networking, battleground-vm]
  affects: [01-02, 01-03, 01-04, phase-02, phase-03]

tech-stack:
  added: [docker-compose, ubuntu-22.04, python-3.11-slim, fastapi, uvicorn, openssh, apache2, mysql, php]
  patterns: [internal-bridge-networks, hub-and-spoke-isolation, entrypoint-service-init]

key-files:
  created:
    - docker-compose.yml
    - orchestrator/Dockerfile
    - orchestrator/main.py
    - agents/red_agent/Dockerfile
    - agents/red_agent/main.py
    - agents/blue_agent/Dockerfile
    - agents/blue_agent/main.py
    - battleground/Dockerfile
    - battleground/setup.sh
    - battleground/sshd_config
    - battleground/entrypoint.sh
  modified: []

decisions:
  - decision: "Used mysql_native_password instead of caching_sha2_password for webapp_user"
    rationale: "caching_sha2_password caused persistent auth failures for PHP/Apache (www-data) connections"
  - decision: "Added chmod 755 /run/mysqld in entrypoint"
    rationale: "MySQL socket directory was 700 (mysql:mysql), blocking www-data from connecting"
  - decision: "Simplified user passwords (removed special chars like ! and #)"
    rationale: "Special characters were unreliably handled during Docker build chpasswd"

metrics:
  duration: "~12 minutes"
  completed: "2026-04-08"
---

# Phase 01 Plan 01: Docker Infrastructure Summary

Docker Compose with 4 services, 3 isolated networks, realistic Ubuntu battleground with SSH + Apache/PHP + MySQL + cron + seeded logs.

## What Was Built

### Task 1: Docker Compose + Dockerfiles
- `docker-compose.yml` with 4 services and 3 networks
- `red-net` (internal) - red-agent + orchestrator only
- `blue-net` (internal) - blue-agent + orchestrator only
- `orchestrator-net` (bridge) - orchestrator + battleground
- Orchestrator: FastAPI /health endpoint on port 8000
- Red agent: Python with nmap, netcat, ping
- Blue agent: Python with auditd, net-tools, ping
- Healthchecks on battleground (SSH) and orchestrator (HTTP)

### Task 2: Battleground VM + Network Isolation
- Ubuntu 22.04 with SSH, Apache/PHP, MySQL, cron
- 4 system users: admin (sudo), webdev, dbadmin, backup
- Vulnerable PHP login page with SQL injection (training target)
- MySQL `webapp` database with 4 seeded user records
- Cron: backup script (backup user), log rotation (root)
- Seeded auth.log (5 entries) and webapp.log (5 entries)
- Network isolation verified: red/blue agents cannot communicate

## Verification Results

| Test | Result |
|------|--------|
| docker compose build | All 4 images built |
| docker compose up -d | All 4 containers running, 2 healthy |
| Red -> Blue ping | FAIL (expected - isolated) |
| Blue -> Red ping | FAIL (expected - isolated) |
| Orchestrator SSH to battleground | SUCCESS |
| Web app (curl localhost:80) | Corporate Portal Login page |
| MySQL webapp.users | 4 records |
| Cron jobs | 2 configured |
| Log files | auth.log + webapp.log seeded |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] MySQL caching_sha2_password auth failure**
- Found during: Task 2
- Issue: PHP running as www-data could not authenticate to MySQL using caching_sha2_password plugin
- Fix: Switched to mysql_native_password for webapp_user
- Files modified: battleground/setup.sh, battleground/entrypoint.sh

**2. [Rule 1 - Bug] MySQL socket directory permissions**
- Found during: Task 2
- Issue: /run/mysqld was 700 (mysql:mysql), www-data couldn't access socket
- Fix: Added chmod 755 /run/mysqld in entrypoint.sh
- Files modified: battleground/entrypoint.sh

**3. [Rule 1 - Bug] Special characters in chpasswd during Docker build**
- Found during: Task 2
- Issue: Passwords with ! and # were mangled during build-time chpasswd
- Fix: Simplified passwords and used heredoc for chpasswd input
- Files modified: battleground/setup.sh

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | 2b9180c | feat(01-01): docker compose infrastructure with 4 services |
| 2 | f9595bc | feat(01-01): realistic battleground VM with SSH, web app, DB, and network isolation |

## Next Phase Readiness

All infrastructure is operational. Containers start cleanly and networks are isolated. Ready for:
- 01-02: KoboldCpp integration (host.docker.internal:5001)
- 01-03: Orchestrator development (FastAPI already running)
- 01-04: Agent development (containers already running with placeholder loops)
