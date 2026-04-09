---
phase: 02-agents-and-game
plan: 04
subsystem: agents
tags: [langgraph, skill-dispatch, game-endpoints, fastapi]

requires:
  - phase: 02-01
    provides: Skill registry with 8 red team skills
  - phase: 02-02
    provides: 10 blue team skills registered
  - phase: 02-03
    provides: Game state machine, scoring engine, snapshot manager, narrative generator
provides:
  - Skill-based tool dispatcher replacing raw command execution in agent loop
  - Skill-aware prompts for red and blue agents
  - 5 game control REST endpoints on orchestrator
  - System role bypass in safety filter for snapshot manager
affects: [02-05, 02-06, phase-3]

tech-stack:
  added: []
  patterns: [skill-dispatch-loop, parse-failure-recovery, game-lifecycle-endpoints]

key-files:
  created: []
  modified:
    - agents/base_agent.py
    - agents/red_agent/agent.py
    - agents/blue_agent/agent.py
    - orchestrator/main.py
    - orchestrator/safety_filter.py

decisions:
  - id: skill-dispatch-over-raw-cmd
    decision: "Replace raw command execution with skill registry dispatch"
    rationale: "Agents pick skills by name; dispatcher executes via registry; no raw shell commands possible"
  - id: parse-failure-recovery
    decision: "3-retry parse failure recovery before forcing default skill"
    rationale: "Gemma may not always produce clean JSON; graceful degradation with hints"
  - id: module-level-game-state
    decision: "Game state as module-level globals in orchestrator"
    rationale: "Single-process demo; acceptable for capstone scope"

metrics:
  duration: ~15min
  completed: 2026-04-09
---

# Phase 02 Plan 04: Agent-Skill Integration and Game Endpoints Summary

Skill-based tool dispatcher replacing raw command execution; 5 game lifecycle endpoints on orchestrator.

## What Was Done

### Task 1: Rewrite base_agent with tool_dispatcher and skill-aware prompts
- Replaced `_parse_llm_response` with `_parse_skill_call` (4-layer JSON extraction)
- Replaced `act_node` with `tool_dispatcher_node` that dispatches to skill registry
- Added `available_skills`, `game_phase`, `parse_failures` to AgentState
- Parse failures loop back to reason with hints (max 3 retries, then default skill)
- Updated red agent prompt: kill chain strategy, escalation on low turns
- Updated blue agent prompt: setup vs battle phase awareness
- Both agents pass role-specific skills via `get_skills_for_role()`

### Task 2: Orchestrator game control endpoints and safety filter
- Added 5 endpoints: POST /game/start, POST /game/advance, GET /game/status, POST /game/score, GET /game/narrative
- Game state managed at module level (GameContext, ScoringEngine, SnapshotManager)
- Score endpoint checks win conditions after each award
- Safety filter: "system" role bypasses role restrictions but global blocklist still applies

## Deviations from Plan

None - plan executed exactly as written.

## Commits

| Commit | Description |
|--------|-------------|
| ebd2249 | feat(02-04): rewrite agents with skill-based tool dispatcher |
| 5d18166 | feat(02-04): add game control endpoints and system role bypass |

## Verification Results

- `_parse_skill_call` correctly parses clean JSON, extracts from mixed text, returns None on garbage
- 5 game routes confirmed in app.routes
- Safety filter system role bypass confirmed (role restrictions skipped, global blocklist enforced)

## Next Phase Readiness

Plan 02-05 (TUI dashboard) can proceed. The game control endpoints provide the data surface for the Rich terminal display. Plan 02-06 (game loop orchestration) can wire the /game/start -> /game/advance -> /game/score flow.
