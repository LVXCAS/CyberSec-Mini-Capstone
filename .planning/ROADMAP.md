# Roadmap: CyberSec AI Capstone — Red vs Blue Autonomous Warfare

**Defined:** 2026-04-08
**Deadline:** 2026-04-10 (2 days)
**Depth:** Comprehensive (compressed to 3 phases for deadline)
**Coverage:** 27/27 v1 requirements mapped

## Overview

Two autonomous AI agents compete over a live Ubuntu VM: a red team attacker and blue team defender powered by Gemma 4 on a single K80 GPU via KoboldCpp. The system runs in Docker, scores in real time, and is demo-ready from a single command. Given the 2-day deadline, phases are designed for maximum parallel execution within each phase — infrastructure and agent core are built simultaneously, game mechanics and agent skills are built simultaneously, and presentation runs in parallel with final integration.

---

## Phase Structure

| Phase | Goal | Requirements | Duration |
|-------|------|--------------|----------|
| 1 - Foundation | Infrastructure and orchestrator are running and proven safe | INFRA-01, INFRA-02, INFRA-03, INFRA-05, AGNT-01, AGNT-03, AGNT-04, AGNT-05 | Day 1 AM |
| 2 - Agents and Game | Both agents execute autonomously and a full game runs to conclusion with scoring | AGNT-02, RED-01, RED-02, RED-03, RED-04, BLUE-01, BLUE-02, BLUE-03, BLUE-04, GAME-01, GAME-02, GAME-03, GAME-04, GAME-05 | Day 1 PM – Day 2 AM |
| 3 - Demo Ready | System is replayable, visually clear, and presentable to a non-technical audience | INFRA-04, PRES-01, PRES-02, PRES-03, PRES-04 | Day 2 |

---

## Phase 1: Foundation

**Goal:** Infrastructure and orchestrator are running and proven safe — agents can execute commands on the battleground through a validated safety layer.

**Dependencies:** None — this is the prerequisite for everything.

**Parallelization:** Docker/networking setup runs in parallel with KoboldCpp/GPU validation.

**Plans:** 4 plans in 3 waves

Plans:
- [ ] 01-01-PLAN.md — Docker Compose infrastructure with network isolation and battleground VM
- [ ] 01-02-PLAN.md — KoboldCpp + Gemma 4 on K80 GPU validation
- [ ] 01-03-PLAN.md — Orchestrator with safety filter, SSH execution, and SQLite logging
- [ ] 01-04-PLAN.md — Autonomous agent reasoning loop with memory, logging, and dedup

### Requirements

| Req | Description |
|-----|-------------|
| INFRA-01 | Docker Compose setup with 3 containers (red-agent, blue-agent, battleground) on isolated networks |
| INFRA-02 | KoboldCpp running Gemma 4 (e2b or e4b) on K80 GPU serving both agents via OpenAI-compatible API |
| INFRA-03 | SSH-based command execution from agents to battleground via orchestrator safety filter |
| INFRA-05 | Agent safety filter — orchestrator validates/sanitizes commands before execution |
| AGNT-01 | Autonomous reasoning loop (observe → reason → act → observe) powered by Gemma 4 |
| AGNT-03 | Short-term memory (rolling context window) + long-term memory (key findings JSON) |
| AGNT-04 | Decision logging capturing every action with reasoning trace |
| AGNT-05 | Turn limit and command deduplication to prevent infinite retry loops |

### Success Criteria

1. Running `docker compose up` brings up all containers and passes a network isolation health check with no agent container able to reach any other agent container directly.
2. KoboldCpp serves Gemma 4 (E2B or E4B) on the K80 GPU and a test prompt returns a valid JSON tool-call response within 30 seconds — confirming CUDA 3.7 compatibility and VRAM headroom for sequential dual-agent inference.
3. A stub agent submits a test command through the orchestrator safety filter, the filter rejects a blocklisted command (e.g., `rm -rf /`), and relays an allowed command via SSH to the battleground, with the result returned to the stub.
4. A single agent completes 3 autonomous turns on the battleground — observe, reason, act — with every decision captured in the JSONL decision log including reasoning trace and exit code.
5. The agent's context window stays within bounds across 3 turns (rolling window truncation working) and no duplicate command is submitted in the same game session.

---

## Phase 2: Agents and Game

**Goal:** Both agents execute real cybersecurity skills autonomously and a complete game runs from blue setup through simultaneous battle to a scored conclusion.

**Dependencies:** Phase 1 complete (inference, orchestrator, and single-agent loop proven).

**Parallelization:** Red team skills and blue team skills can be built in parallel. Game mechanics (phase state machine, scoring) can be built in parallel with agent skill development and wired together at integration.

### Requirements

| Req | Description |
|-----|-------------|
| AGNT-02 | Tool/skill system with defined cybersecurity tools agents can invoke |
| RED-01 | Reconnaissance skills (port scanning, service enumeration) |
| RED-02 | Exploitation skills (service exploits, credential attacks) |
| RED-03 | Privilege escalation skills |
| RED-04 | Persistence skills (backdoor users, cron jobs, SSH keys) |
| BLUE-01 | Hardening skills (firewall rules, service config, user lockdown) |
| BLUE-02 | Detection skills (log monitoring, process watching, connection tracking) |
| BLUE-03 | Response skills (kill processes, remove unauthorized users, block IPs) |
| BLUE-04 | Uptime maintenance (service health checks, restoration) |
| GAME-01 | Phase-based flow — blue setup phase (2-5 min) → simultaneous battle → conclusion |
| GAME-02 | Two-layer scoring — decision log (AI reasoning showcase) + competitive points |
| GAME-03 | Battleground state snapshots every 30-60 seconds |
| GAME-04 | Win conditions — time expiry, red full kill chain, or blue lockout |
| GAME-05 | Detection/stealth bonuses — blue scores for catching stealthy actions, red scores for evasion |

### Success Criteria

1. Red agent completes a 4-step kill chain autonomously (recon → exploit → privilege escalation → persistence) with each step captured in the decision log with reasoning.
2. Blue agent autonomously hardens the VM during the setup phase — firewall rules are applied, a service is hardened, and a detection mechanism is active — all before the battle phase begins.
3. A full game runs from `game start` to a scored conclusion: blue setup phase completes, both agents operate simultaneously for at least 5 minutes, and the game terminates via a win condition (time expiry, kill chain, or lockout).
4. The scoring engine produces a final score summary showing red points, blue points, and the decisive win condition — readable to a non-technical observer from terminal output alone.
5. At least one detection bonus (blue catches a stealthy red action) or stealth bonus (red evades blue) is recorded in a complete test game.

---

## Phase 3: Demo Ready

**Goal:** The system is replayable from a single command, the terminal display communicates what is happening to a non-technical audience, and presentation materials are complete.

**Dependencies:** Phase 2 complete (a full game runs to conclusion).

**Parallelization:** Terminal display polish runs in parallel with slide creation; reset script hardening runs in parallel with replay viewer.

### Requirements

| Req | Description |
|-----|-------------|
| INFRA-04 | One-command game reset — `docker rm` + `docker run` from clean image, validated 5+ times |
| PRES-01 | Rich terminal display showing real-time game progress |
| PRES-02 | Capstone presentation slides with architecture diagram |
| PRES-03 | Post-game log/replay viewer |
| PRES-04 | Architecture diagram for slides |

### Success Criteria

1. Running `./reset.sh && ./start.sh` five times in a row each produces a clean game start from a fresh battleground state — no artifacts from previous runs visible in the second game.
2. The terminal display shows both agents' actions and scores simultaneously in real time during a live game, legible to someone who has never seen the codebase.
3. A completed game's decision log can be replayed in the terminal with simulated timing, showing the full narrative of the game without re-running the model.
4. The presentation slides contain an architecture diagram, an explanation of the scoring system, and a live demo section — sufficient to present the capstone without verbal scaffolding.

---

## Coverage Validation

| Requirement | Phase |
|-------------|-------|
| INFRA-01 | Phase 1 |
| INFRA-02 | Phase 1 |
| INFRA-03 | Phase 1 |
| INFRA-04 | Phase 3 |
| INFRA-05 | Phase 1 |
| AGNT-01 | Phase 1 |
| AGNT-02 | Phase 2 |
| AGNT-03 | Phase 1 |
| AGNT-04 | Phase 1 |
| AGNT-05 | Phase 1 |
| RED-01 | Phase 2 |
| RED-02 | Phase 2 |
| RED-03 | Phase 2 |
| RED-04 | Phase 2 |
| BLUE-01 | Phase 2 |
| BLUE-02 | Phase 2 |
| BLUE-03 | Phase 2 |
| BLUE-04 | Phase 2 |
| GAME-01 | Phase 2 |
| GAME-02 | Phase 2 |
| GAME-03 | Phase 2 |
| GAME-04 | Phase 2 |
| GAME-05 | Phase 2 |
| PRES-01 | Phase 3 |
| PRES-02 | Phase 3 |
| PRES-03 | Phase 3 |
| PRES-04 | Phase 3 |

**Total mapped: 27/27**

---

## Progress

| Phase | Status | Completed |
|-------|--------|-----------|
| 1 - Foundation | Planned (4 plans) | — |
| 2 - Agents and Game | Not started | — |
| 3 - Demo Ready | Not started | — |

---

## Dependency Graph

```
Phase 1: Foundation
  ├── Docker + Networking (parallel)
  └── KoboldCpp + GPU Validation (parallel)
        │
        ▼
Phase 2: Agents and Game
  ├── Red Team Skills (parallel)
  ├── Blue Team Skills (parallel)
  └── Game Mechanics + Scoring (parallel)
        │
        ▼
Phase 3: Demo Ready
  ├── Terminal Display Polish (parallel)
  ├── Reset Script Hardening (parallel)
  ├── Replay Viewer (parallel)
  └── Presentation Slides (parallel)
```

---

## Critical Path (2-Day Deadline)

**Day 1 AM:** Phase 1 — infrastructure, KoboldCpp on K80, orchestrator, single-agent loop
**Day 1 PM – Day 2 AM:** Phase 2 — agent skills, game mechanics, dual-agent play, scoring
**Day 2:** Phase 3 — demo polish, reset hardening, slides, replay viewer

**Single most critical validation (do first):** `nvidia-smi` + KoboldCpp CUDA 3.7 compatibility + Gemma 4 E4B VRAM benchmark. Everything else depends on this.

---
*Roadmap defined: 2026-04-08*
*Last updated: 2026-04-08 — Phase 1 planned (4 plans, 3 waves)*
