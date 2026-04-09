# Project State: CyberSec AI Capstone

**Last updated:** 2026-04-09
**Session:** Phase 2 in progress — 02-01, 02-02, 02-03, 02-04, 02-05 complete

---

## Project Reference

**Core value:** Autonomous AI agents that reason about cybersecurity decisions and execute real commands on real infrastructure — proving AI can independently attack and defend systems without human guidance.

**Current focus:** Phase 2 — Agent Skills + Game Mechanics (02-01 through 02-05 complete)

**Deadline:** 2026-04-10 (2 days from now)

---

## Current Position

| Field | Value |
|-------|-------|
| Milestone | v1 |
| Phase | 2 — Agents and Game (in progress) |
| Plan | 02-05 complete |
| Status | In progress |
| Last activity | 2026-04-09 - Completed 02-05-PLAN.md |
| Progress | ████████░░ 80% |

**Phase progress:** Phase 2 plans 1-5 of 6 complete

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Requirements defined | 27 |
| Requirements mapped | 27 |
| Requirements complete | 8 |
| Phases complete | 1/3 |

---

## Accumulated Context

### Key Decisions Made

| Decision | Rationale | Status |
|----------|-----------|--------|
| Mock _log_decision in host tests | Docker-only /app/data path; mocking isolates parsing logic | Confirmed |
| 3-phase compression (from 6) | 2-day deadline demands aggressive phase combining | Confirmed |
| Parallel execution within phases | Red/blue skills and game mechanics built simultaneously in Phase 2 | Confirmed |
| mysql_native_password for PHP | caching_sha2_password fails for www-data socket connections | Confirmed |
| Simplified container passwords | Special chars unreliable in Docker build chpasswd | Confirmed |
| INFRA-04 (reset) in Phase 3 | Reset script belongs to demo readiness, not infrastructure skeleton | Confirmed |
| Kobalt over Ollama | K80 CUDA 3.7 — Ollama and vLLM require CUDA 8.0+ | Confirmed |
| E4B variant approved | User approved at 01-02 checkpoint; fits 24GB K80 VRAM | Confirmed |
| Hub-and-spoke orchestrator | Agents never touch battleground directly — orchestrator proxies all commands | Confirmed |
| Skills POST to orchestrator /execute | Maintains hub-and-spoke; orchestrator handles SSH, safety, logging | Confirmed |
| Skill dispatch over raw commands | Agents pick skills by name; no raw shell commands possible | Confirmed |
| 3-retry parse failure recovery | Gemma may not produce clean JSON; graceful degradation with hints | Confirmed |
| Module-level game state in orchestrator | Single-process demo; acceptable for capstone scope | Confirmed |
| Blocklist safety filter | Demo needs visible blocked commands; allowlist too restrictive for exploratory agents | Confirmed |
| 4096 char output truncation | Prevents LLM context explosion from large command outputs | Confirmed |
| WAL mode SQLite | Allows concurrent reads from multiple agents without blocking | Confirmed |
| Sequential inference | One KoboldCpp instance serves both agents sequentially — only safe option for 24GB K80 | Confirmed |
| LangGraph for agent loop | Explicit, auditable state graph; auditable, replayable vs CrewAI's opaque roles | Confirmed |
| FastAPI orchestrator | Async, Pydantic-native, OpenAPI docs useful for demo | Confirmed |
| SQLite for game log | Zero-dependency, file-based, sufficient for bounded simulation | Confirmed |
| Rich for terminal display | Faster to ship than web frontend; equally compelling for capstone | Confirmed |
| List for executed_commands | JSON serialisation; LangGraph state must be serialisable | Confirmed |
| Regex fallback for LLM parsing | Gemma 4 may not always produce clean JSON; graceful degradation needed | Confirmed |

### Critical Unknowns (Validate in Phase 1 First)

- K80 VRAM empirical headroom with Gemma 4 E4B Q4_K_M (two sequential contexts)
- KoboldCpp CUDA 3.7 binary compatibility (may need to build from source)
- Gemma 4 tool-call format via KoboldCpp (may need structured JSON fallback)
- E2B vs E4B quality — test both with real game prompts before committing

### Architecture Confirmed

- **Stack:** LangGraph + KoboldCpp + FastAPI + Paramiko + Docker Compose + Rich + SQLite
- **Pattern:** Hub-and-spoke orchestrator; agents never communicate directly
- **Containers:** 3 (red-agent, blue-agent, battleground) + KoboldCpp inference server
- **Safety:** Allowlist filter in orchestrator; no docker.sock mounts; bridge networks only
- **Inference:** Sequential — only one agent generates at a time; max 2048 input + 512 output tokens per turn

### Blockers

None currently.

### Open Todos

- [ ] Validate K80 VRAM before any development (highest priority action)
- [ ] Confirm KoboldCpp CUDA 3.7 binary or determine if build from source needed
- [ ] Run `/gsd:plan-phase 1` to break Phase 1 into executable tasks

---

## Session Continuity

### To Resume

1. Read this file for current position
2. Read `/Users/lvxcas/Cyber Capstone/.planning/ROADMAP.md` for phase goals and success criteria
3. Next plan: `.planning/phases/01-foundation/01-04-PLAN.md`

### Session Log

- 2026-04-08: Project initialized, roadmap finalized
- 2026-04-08: Completed 01-01 (Docker infrastructure) - 2 tasks, 2 commits
- 2026-04-08: Completed 01-02 (KoboldCpp + Gemma 4 inference) - 2 tasks + checkpoint, 2 commits
- 2026-04-08: Completed 01-03 (Orchestrator + safety filter + SSH + SQLite) - 2 tasks, 2 commits
- 2026-04-08: Completed 01-04 (Autonomous agent reasoning loop) - 2 tasks, 2 commits — Phase 1 complete
- 2026-04-08: Completed 01-05 (Dockerfiles + env secrets) - gap closure 1/2
- 2026-04-08: Completed 01-06 (Network isolation test script) - gap closure 2/2
- 2026-04-08: Completed 01-07 (Act node response parsing fix) - gap closure 3/3
- 2026-04-08: Phase 1 verified ✓ (5/5 must-haves, human_needed for hardware tests, approved)
- 2026-04-09: Completed 02-01 (Skill registry + 8 red team skills) - 2 tasks, 2 commits

Last session: 2026-04-09
Stopped at: Completed 02-04-PLAN.md
Resume file: None

---
*State initialized: 2026-04-08*
*Last updated: 2026-04-09 — 02-04 Agent-skill integration + game endpoints complete*
