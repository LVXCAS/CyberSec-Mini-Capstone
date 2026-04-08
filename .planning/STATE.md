# Project State: CyberSec AI Capstone

**Last updated:** 2026-04-08
**Session:** Plan 01-01 complete

---

## Project Reference

**Core value:** Autonomous AI agents that reason about cybersecurity decisions and execute real commands on real infrastructure — proving AI can independently attack and defend systems without human guidance.

**Current focus:** Phase 1 — Foundation (infrastructure, KoboldCpp, orchestrator, single-agent loop)

**Deadline:** 2026-04-10 (2 days from now)

---

## Current Position

| Field | Value |
|-------|-------|
| Milestone | v1 |
| Phase | 1 — Foundation |
| Plan | 01-01 complete |
| Status | In progress |
| Last activity | 2026-04-08 - Completed 01-01-PLAN.md |
| Progress | █░░░░░░░░░ 8% |

**Phase progress:** 0/3 phases complete (1/4 plans done in Phase 1)

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Requirements defined | 27 |
| Requirements mapped | 27 |
| Requirements complete | 3 |
| Phases complete | 0/3 |

---

## Accumulated Context

### Key Decisions Made

| Decision | Rationale | Status |
|----------|-----------|--------|
| 3-phase compression (from 6) | 2-day deadline demands aggressive phase combining | Confirmed |
| Parallel execution within phases | Red/blue skills and game mechanics built simultaneously in Phase 2 | Confirmed |
| mysql_native_password for PHP | caching_sha2_password fails for www-data socket connections | Confirmed |
| Simplified container passwords | Special chars unreliable in Docker build chpasswd | Confirmed |
| INFRA-04 (reset) in Phase 3 | Reset script belongs to demo readiness, not infrastructure skeleton | Confirmed |
| Kobalt over Ollama | K80 CUDA 3.7 — Ollama and vLLM require CUDA 8.0+ | Confirmed |
| Hub-and-spoke orchestrator | Agents never touch battleground directly — orchestrator proxies all commands | Confirmed |
| Sequential inference | One KoboldCpp instance serves both agents sequentially — only safe option for 24GB K80 | Confirmed |
| LangGraph for agent loop | Explicit, auditable state graph; auditable, replayable vs CrewAI's opaque roles | Confirmed |
| FastAPI orchestrator | Async, Pydantic-native, OpenAPI docs useful for demo | Confirmed |
| SQLite for game log | Zero-dependency, file-based, sufficient for bounded simulation | Confirmed |
| Rich for terminal display | Faster to ship than web frontend; equally compelling for capstone | Confirmed |

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
3. Next plan: `.planning/phases/01-foundation/01-02-PLAN.md`

### Session Log

- 2026-04-08: Project initialized, roadmap finalized
- 2026-04-08: Completed 01-01 (Docker infrastructure) - 2 tasks, 2 commits

Last session: 2026-04-08
Stopped at: Completed 01-01-PLAN.md
Resume file: .planning/phases/01-foundation/01-02-PLAN.md

---
*State initialized: 2026-04-08*
*Last updated: 2026-04-08 — plan 01-01 complete*
