---
phase: "01"
plan: "05"
subsystem: infrastructure
tags: [docker, langgraph, security, env, containers]

dependency-graph:
  requires: ["01-04"]
  provides: ["working-agent-containers", "secret-management"]
  affects: ["02-skills"]

tech-stack:
  added: []
  patterns: ["build-context-parent-dir", "env-file-secrets"]

key-files:
  created:
    - .env
    - .env.example
  modified:
    - agents/red_agent/Dockerfile
    - agents/blue_agent/Dockerfile
    - agents/red_agent/main.py
    - agents/blue_agent/main.py
    - docker-compose.yml
    - orchestrator/ssh_executor.py
    - .gitignore

decisions:
  - id: build-context-agents
    choice: "Build context set to ./agents (parent dir) not ./agents/red_agent"
    rationale: "Docker COPY cannot reference parent directories; widening context to ./agents allows COPY base_agent.py and requirements.txt"
  - id: password-validation
    choice: "Raise ValueError if BATTLEGROUND_PASSWORD missing"
    rationale: "Fail fast at startup rather than silently failing SSH connections later"

metrics:
  duration: "~10 minutes"
  completed: "2026-04-08"
---

# Phase 01 Plan 05: Gap Closure — Dockerfiles and Env Summary

**One-liner:** Fixed agent containers to install LangGraph deps and run agent.py (not sleep loop), and moved hardcoded password to gitignored .env file.

## What Was Built

Two gap closure fixes identified in post-phase verification:

1. **Agent Dockerfiles** — previously copied only `main.py` which contained a sleep-forever stub. Containers never exercised agent logic. Fixed by:
   - Widening docker-compose build context from `./agents/red_agent` to `./agents`
   - Updating Dockerfiles to install `requirements.txt` (langgraph, langchain-core, requests, pydantic)
   - Copying `base_agent.py`, `agent.py`, and `main.py` from correct paths
   - Setting `CMD ["python", "agent.py"]` so the LangGraph reasoning loop runs
   - Replacing sleep-stub `main.py` with a proper delegation wrapper

2. **Secret management** — hardcoded `Pr0jectAdmin1` appeared in docker-compose.yml and ssh_executor.py. Fixed by:
   - Creating `.env` with `BATTLEGROUND_PASSWORD` value
   - Creating `.env.example` with placeholder (committed, safe)
   - Adding `.env` to `.gitignore`
   - Updating docker-compose.yml to use `${BATTLEGROUND_PASSWORD}` interpolation
   - Updating ssh_executor.py to remove hardcoded fallback and raise `ValueError` if var is absent

## Verification Results

- `docker compose build red-agent blue-agent` — both built successfully
- `docker compose run --rm red-agent python -c "from base_agent import run_agent; print('OK')"` — output: OK
- `docker compose run --rm blue-agent python -c "from base_agent import run_agent; print('OK')"` — output: OK
- `grep -r "Pr0jectAdmin1" . --include="*.py" --include="*.yml"` — zero results
- `grep "BATTLEGROUND_PASSWORD" .env` — shows value present
- `grep ".env" .gitignore` — .env is ignored

## Deviations from Plan

None — plan executed exactly as written.

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Build context `./agents` (not `./agents/red_agent`) | Docker cannot COPY from parent dirs; widening context is the correct approach |
| `raise ValueError` on missing env var | Fail fast at process start rather than surfacing a confusing SSH auth error |

## Next Phase Readiness

Phase 2 (Agent Skills + Game Mechanics) can now proceed. Agent containers:
- Install all required Python dependencies
- Run the actual LangGraph reasoning loop
- Have no hardcoded secrets
