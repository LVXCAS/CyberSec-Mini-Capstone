---
phase: 02-agents-and-game
plan: 01
subsystem: skills
tags: [red-team, nmap, hydra, suid, persistence, skill-registry]
dependency-graph:
  requires: [01-foundation]
  provides: [SKILL_REGISTRY, red-team-skills]
  affects: [02-04-tool-dispatcher, 02-03-agent-prompts]
tech-stack:
  added: []
  patterns: [hub-and-spoke-execution, skill-registry-pattern]
key-files:
  created:
    - skills/__init__.py
    - skills/registry.py
    - skills/red/__init__.py
    - skills/red/recon.py
    - skills/red/exploit.py
    - skills/red/privesc.py
    - skills/red/persistence.py
  modified: []
decisions:
  - id: d-0201-01
    decision: "All skills POST to orchestrator /execute rather than running commands directly"
    rationale: "Maintains hub-and-spoke pattern; orchestrator handles SSH, safety filtering, and logging"
  - id: d-0201-02
    decision: "Shared _execute_on_orchestrator helper duplicated per module instead of shared util"
    rationale: "Each module is self-contained; avoids circular imports; helper is small (~15 lines)"
metrics:
  duration: "~5 min"
  completed: 2026-04-09
---

# Phase 02 Plan 01: Skill Registry and Red Team Skills Summary

**One-liner:** Skill registry framework with 8 red team skills covering recon, exploit, privesc, and persistence — all routing through orchestrator /execute endpoint.

## What Was Done

### Task 1: Skill registry + red recon and exploit skills
- Created `skills/registry.py` with `SKILL_REGISTRY` dict, `get_skills_for_role()`, and `execute_skill()` functions
- Created `skills/red/recon.py` with `port_scan` (nmap TCP connect scan) and `service_enum` (nmap scripts)
- Created `skills/red/exploit.py` with `ssh_brute` (hydra) and `web_sqli_check` (curl SQLi test)
- Commit: `0270137`

### Task 2: Red privesc and persistence skills
- Created `skills/red/privesc.py` with `find_suid` (filters known-safe SUID binaries)
- Created `skills/red/persistence.py` with `add_backdoor_user`, `install_cron_backdoor`, `add_ssh_key`
- Registered all 8 skills in registry
- Commit: `80e6a84`

## Verification Results

- 8 skills registered in SKILL_REGISTRY
- All skills have docstrings and type annotations
- No direct subprocess or paramiko imports — all go through orchestrator
- `get_skills_for_role("red")` returns metadata suitable for LLM prompts

## Deviations from Plan

None — plan executed exactly as written.

## Decisions Made

1. **Hub-and-spoke execution only** — Skills never SSH directly; they POST commands to the orchestrator which handles SSH, safety filtering, and logging.
2. **Per-module helper function** — `_execute_on_orchestrator` is duplicated in each skill module rather than shared, keeping modules self-contained.

## Next Phase Readiness

- Registry ready for blue team skills (Plan 02)
- Registry ready for tool dispatcher integration (Plan 04)
- `get_skills_for_role("red")` output ready for agent prompt construction (Plan 03)
