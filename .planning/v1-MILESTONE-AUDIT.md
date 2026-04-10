---
milestone: v1
audited: 2026-04-09
status: gaps_found
scores:
  requirements: 24/27 satisfied structurally (3 need hardware runtime)
  phases: 3/3 phase verifications passed (P1 human_needed, P2/P3 passed)
  integration: 3 blockers + 3 high-severity data contract breaks
  flows: 4/7 E2E flows BROKEN
gaps:
  integration:
    - "B1: game/loop.py::run_game is orphaned — no script, endpoint, or container entrypoint ever invokes it. reset.sh/start.sh only bring up compose."
    - "B2: Two contradictory execution models — red-agent/blue-agent containers autonomously run 15-turn battle loops at startup, while game/loop.py also spawns agent graphs via _run_agent_turn. No coordination; phase-based setup→battle is never enforced."
    - "B3: Agent containers cannot reach inference server. base_agent uses host.docker.internal:5001 but red-agent/blue-agent are on internal:true networks with no extra_hosts/host-gateway. LLM calls silently fail → fallback to _DEFAULT_SKILLS every turn."
  data_contracts:
    - "H1: game/loop.py _RED_SCORE_MAP and _BLUE_SCORE_MAP reference skill names that do NOT exist in the registry (web_sql_inject vs web_sqli_check, install_backdoor vs install_cron_backdoor, check_auth_logs vs tail_auth_log, check_suid vs fix_suid, etc.). Scoring will silently award zero for most actions; stealth-bonus logic always says 'not detected' → red gets free stealth bonuses every turn."
    - "H2: _run_agent_turn(current_turn+1) passes max_turns but run_agent always starts turn_number=0, so each 'single turn' actually runs N cycles from scratch. No cross-turn memory; dedup resets every turn; O(n²) work."
    - "H3: Blue skills register orchestrator_url as an LLM-visible parameter. execute_skill injects it as kwarg → double-kwarg TypeError if LLM passes it back. Red skills correctly exclude it."
  requirements_needing_runtime:
    - "INFRA-01: Docker network isolation (needs docker runtime)"
    - "INFRA-02: KoboldCpp + Gemma 4 on K80 (needs GPU hardware)"
    - "GAME-05 live: detection/stealth bonus triggering (needs live game — blocked by B1–H1)"
tech_debt:
  - phase: 01-foundation
    items:
      - "act_node parsing was fixed in 01-07 but regression coverage limited"
  - phase: 03-demo-ready
    items:
      - "No global /decisions endpoint (replay.py queries per-role instead — functional but spec mismatch)"
      - "red/blue agent.py use fragile sys.path.insert for base_agent import"
---

# Milestone v1 Audit — CyberSec AI Capstone

**Audited:** 2026-04-09
**Status:** ⚠ GAPS FOUND — critical blockers prevent E2E demo flow
**Phases:** 3/3 phase-level verifications passed (Phase 1 with human-verification caveats)

## Executive Summary

Phase-level verifications all passed (Phase 1 human_needed for hardware, Phases 2 & 3 passed). However, cross-phase integration checking reveals **3 critical blockers and 3 high-severity data contract breaks** that will prevent the canonical E2E flow (reset → start → game_start → phased battle → scoring → narrative → replay) from running correctly in a live demo.

Each phase built its contracts in isolation. The seams between phases were not exercised end-to-end.

## Requirements Coverage

| Count | Status |
|-------|--------|
| 24/27 | Structurally satisfied in code |
| 2/27 | Require hardware runtime (INFRA-01, INFRA-02) |
| 1/27 | Requires live game to observe (GAME-05) — blocked by integration gaps |

## Critical Blockers (from integration checker)

### B1 — `game/loop.py::run_game` is orphaned dead code
`run_game` is defined but never called. `scripts/start.sh` and `scripts/reset.sh` only bring up docker compose + health-wait. Nothing POSTs `/game/start` or walks the state machine. **The advertised demo flow does not actually run.**

### B2 — Two contradictory execution models
`docker-compose.yml` starts `red-agent` and `blue-agent` as long-running containers that each call `run_agent(..., game_phase="battle", max_turns=15)` at startup. `game/loop.py` expects to orchestrate turn alternation itself. Both systems coexist with no reconciliation — if `run_game` were invoked, it would spawn agent graphs in-process while the agent containers continued running their own independent battle loops.

### B3 — Agents cannot reach the inference server
`base_agent.INFERENCE_URL = http://host.docker.internal:5001`. Red/blue agent containers are attached to `red-net` / `blue-net` with `internal: true`, no `extra_hosts`, no bridge. Only the orchestrator has `host.docker.internal`. Every `reason_node` HTTP call from agent containers fails → silent fallback to `_DEFAULT_SKILLS` (`port_scan 10.0.0.5` / `scan_processes`) every turn. **No real LLM reasoning happens in the demo.**

## High-Severity Data Contract Breaks

### H1 — Scoring maps reference non-existent skill names
`game/loop.py` lines 23–45 reference skills that don't exist in the registry:

| In scoring map | Actual registry name |
|---|---|
| `web_sql_inject` | `web_sqli_check` |
| `install_backdoor` / `create_persistence` | `install_cron_backdoor`, `add_backdoor_user`, `add_ssh_key` |
| `exfil_data`, `web_dir_enum` | — (do not exist) |
| `configure_firewall`, `detect_intrusion`, `check_file_integrity` | — (do not exist) |
| `check_auth_logs` | `tail_auth_log` |
| `check_suid` | `fix_suid` |
| `remove_backdoor` | `remove_user` |

Only 3 red skills (`port_scan`, `ssh_brute`, `find_suid`) and 4 blue skills (`harden_ssh`, `block_ip`, `scan_processes`, `kill_process`) match. Everything else silently awards zero points. Stealth-detection logic keys off the same wrong names → red receives stealth bonuses every turn because the "detection" signal never fires.

### H2 — `_run_agent_turn` spawns fresh graphs per turn
`max_turns=current_turn+1` but `run_agent` initializes `turn_number=0` each call. On battle turn 10 the agent runs 11 observe→reason→dispatch cycles from scratch, with findings / observations / dedup hash list reset. The alternating-turn game is effectively N independent fresh agent runs of increasing length.

### H3 — Blue skills expose `orchestrator_url` as an LLM parameter
`skills/blue/__init__.py` registers `orchestrator_url` in every skill's `parameters` dict. It ends up in `skills_json` → LLM prompt → LLM emits it in tool calls → `execute_skill` also injects it as kwarg → `TypeError: multiple values for keyword argument 'orchestrator_url'`. Red skills correctly exclude it.

## Cross-Phase E2E Flow Results

| Flow | Status | Break point |
|---|---|---|
| Full game (reset → start → game_start → setup → battle → conclusion) | BROKEN | No script invokes `/game/start` or `run_game` (B1) |
| Agent action loop inside containers | BROKEN | No route from red/blue networks to inference (B3) — silent fallback |
| Alternating red/blue turns with phased setup | BROKEN | `run_game` never called; containers run uncoordinated (B2) |
| Scoring on skill success | BROKEN | Skill name mismatches (H1) |
| Replay flow (SQLite → replay.py → dashboard) | FUNCTIONAL (if game ran) | Works mechanically; empty until B1–B3 fixed |
| Live dashboard polling | FUNCTIONAL | `/game/status` + `/decisions/{role}` wired; shows empty state |
| reset.sh → docker-compose services | OK | Service set matches |

## Phase-Level Tech Debt

- **Phase 1:** `act_node` parsing fix (01-07) has 3 regression tests; fuller coverage optional
- **Phase 3:** No global `/decisions` endpoint (replay queries per-role); fragile `sys.path.insert` in red/blue agent entry points

## Minimum Fixes for a Working Demo

1. Remove red-agent/blue-agent services from docker-compose (or make them idle), OR remove `run_game` and make the autonomous-container model the real flow
2. Create an entrypoint that actually invokes `run_game` — a `scripts/run-game.sh` or a `/game/run` orchestrator endpoint — and wire `start.sh` to call it
3. Add `extra_hosts: host.docker.internal:host-gateway` to the process that runs agent graphs, or run it inside the orchestrator container (which already has host access)
4. Fix `_RED_SCORE_MAP`/`_BLUE_SCORE_MAP` to use registered skill names; add correct stealth-detection keys
5. Fix `_run_agent_turn` to carry state across turns (or accept the fresh-graph model and change the comment + metrics accordingly)
6. Strip `orchestrator_url` from blue skill `parameters` metadata

---

*Audited by: gsd-integration-checker + /gsd:audit-milestone orchestrator*
