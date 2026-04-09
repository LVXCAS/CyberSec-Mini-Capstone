---
phase: 03
plan: 02
subsystem: demo-scripts
tags: [bash, docker, reset, demo, health-check]
requires: [docker-compose.yml, orchestrator /health endpoint]
provides: [scripts/reset.sh, scripts/start.sh, scripts/demo.sh, scripts/validate-reset.sh]
affects: [03-03, 03-04]
tech-stack:
  added: []
  patterns: [docker compose down -v teardown, curl health poll, 5-cycle idempotency validation]
key-files:
  created:
    - scripts/reset.sh
    - scripts/start.sh
    - scripts/demo.sh
    - scripts/validate-reset.sh
  modified: []
decisions:
  - "curl health poll instead of docker health status — simpler and works regardless of HEALTHCHECK config"
  - "120s timeout for health wait — sufficient for build + startup on slower machines"
  - "validate-reset.sh checks /game/status scores sum to 0 — verifies volume wipe worked"
metrics:
  duration: "5 minutes"
  completed: "2026-04-09"
---

# Phase 3 Plan 02: Demo Scripts Summary

**One-liner:** Four bash scripts (reset, start, demo, validate) enabling one-command teardown, rebuild, and 5-cycle idempotency validation via docker compose down -v and curl health poll.

## What Was Built

Four scripts in `scripts/` implementing INFRA-04 (replayable demo from single command):

- `scripts/reset.sh` — tears down all containers and volumes (`docker compose down -v --remove-orphans`), rebuilds from scratch (`up --build -d`), polls `http://localhost:8000/health` until healthy (120s timeout)
- `scripts/start.sh` — brings up existing images (`docker compose up -d`), polls health before exiting
- `scripts/demo.sh` — chains `reset.sh` then launches `python -m display.dashboard` foreground
- `scripts/validate-reset.sh` — runs 5 consecutive `reset.sh` cycles, checking health and zero stale game scores after each

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Reset and start scripts | 5432d9e | scripts/reset.sh, scripts/start.sh |
| 2 | Demo script combining reset + start + dashboard | 426712e | scripts/demo.sh |
| 3 | Validation script for 5 consecutive resets | 73596a3 | scripts/validate-reset.sh |

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| curl health poll (not docker health status) | Works without parsing JSON from `docker compose ps`; simpler and more portable |
| 120s timeout | Accounts for image rebuild time on first run |
| validate-reset checks scores sum | Direct evidence of clean game state, not just container health |

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

- All four scripts pass `bash -n` syntax check
- `grep -q "down -v" scripts/reset.sh` passes
- `grep -q "health" scripts/start.sh` passes
- All scripts use `set -euo pipefail` and `cd "$(dirname "$0")/.."` to project root

## Next Phase Readiness

Plan 03-03 and 03-04 can now reference `./scripts/reset.sh` and `./scripts/start.sh` as stable entry points for demo setup. The validate-reset.sh script provides the 5-run idempotency proof required by INFRA-04.
