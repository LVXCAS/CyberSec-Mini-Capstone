# CyberSec AI Capstone — Red vs Blue Autonomous Warfare

**Project:** Mini Capstone · Cybersecurity Program
**Version:** v1 (2026-04)
**Repository:** https://github.com/LVXCAS/CyberSec-Mini-Capstone

---

## 1. Overview

CyberSec AI Capstone is a live cybersecurity simulation in which two autonomous AI agents — a **Red Team attacker** and a **Blue Team defender** — compete over a fresh Ubuntu "battleground" VM using real shell commands. Neither agent is scripted: each reasons about its situation, selects a skill from its toolbox, and executes real commands through a safety-filtered orchestrator. The goal of the project is to demonstrate that modestly-sized local language models (Gemma 4, ~2B–4B parameters) can independently drive an attack/defense loop against a live Linux host and produce a visibly legible game from start to finish.

The system runs entirely locally on a server with a 24 GB NVIDIA K80 GPU. Inference is served by **KoboldCpp** (the CUDA 11/cc3.7-compatible build) via an OpenAI-compatible HTTP API shared by both agents. There are no cloud API calls.

## 2. Architecture

```
                    ┌────────────────────────────┐
                    │   KoboldCpp + Gemma 4      │
                    │   (host:5001, K80 GPU)     │
                    └──────────────┬─────────────┘
                                   │ OpenAI-compat chat/completions
            ┌──────────────────────┼──────────────────────┐
            │                      │                      │
    ┌───────▼────────┐     ┌───────▼────────┐     ┌───────▼────────┐
    │   red-agent    │     │  orchestrator  │     │   blue-agent   │
    │ (LangGraph +   │     │  FastAPI +     │     │ (LangGraph +   │
    │  base_agent)   │     │  safety_filter │     │  base_agent)   │
    └───────┬────────┘     │  SSH executor  │     └───────┬────────┘
            │              │  SQLite log    │             │
       red-net (isolated)  │  Game engine   │       blue-net (isolated)
            │              └───────┬────────┘             │
            └──────────────────────┼──────────────────────┘
                                   │ SSH (password auth from env)
                            ┌──────▼──────┐
                            │ battleground│
                            │ Ubuntu VM   │
                            └─────────────┘
```

**Four Docker services** (`docker-compose.yml`) on three isolated networks (`red-net`, `blue-net`, `orchestrator-net`). Red and blue networks are declared `internal: true` so the agents cannot reach each other or the outside world directly — all traffic flows through the orchestrator. The orchestrator is the single privileged component: it validates every command against a 14-pattern blocklist plus role-based restrictions, executes allowed commands on the battleground over SSH (`paramiko`), and logs every decision to SQLite.

**Agent reasoning loop** (`agents/base_agent.py`) is a LangGraph state machine with four nodes: `observe → reason → tool_dispatcher → check_done`. `observe` fetches recent decision history from the orchestrator; `reason` calls the LLM with a role-specific system prompt, the rolling observation window (capped at 5 entries) and the JSON skill catalog, and parses the tool call with a three-layer recovery strategy (strict JSON → regex extraction → default skill). `tool_dispatcher` calls the shared `skills.registry` which executes one of 17 registered skills (7 red + 10 blue). `check_done` enforces `max_turns` and a deduplication list so a stuck agent cannot loop on the same command.

**Game engine** (`game/loop.py`, `game/state.py`, `game/scoring.py`, `game/narrative.py`) implements a three-phase lifecycle: **SETUP** (blue-only hardening turns, time-bounded to ~2–5 min), **BATTLE** (alternating red/blue turns until a win condition fires), and **CONCLUSION** (narrative + score rollup). `ScoringEngine` awards points from a 15-entry event dictionary covering recon, access, privesc, persistence, hardening, detection, response, and uptime, plus a two-turn sliding window for stealth/detection bonuses.

## 3. Skills

| Role  | Category      | Skills                                                         |
| ----- | ------------- | -------------------------------------------------------------- |
| Red   | Recon         | `port_scan`, `service_enum`                                    |
| Red   | Exploit       | `ssh_brute`, `web_sqli_check`                                  |
| Red   | Privesc       | `find_suid`                                                    |
| Red   | Persistence   | `add_backdoor_user`, `install_cron_backdoor`, `add_ssh_key`    |
| Blue  | Hardening     | `harden_ssh`, `block_ip`, `fix_suid`                           |
| Blue  | Detection     | `scan_processes`, `tail_auth_log`, `list_users`                |
| Blue  | Response      | `kill_process`, `remove_user`                                  |
| Blue  | Uptime        | `check_service`, `restart_service`                             |

Each skill wraps a real binary on the battleground (nmap, hydra, sqlmap, iptables, systemctl, etc.) and dispatches via the orchestrator `/execute` endpoint, which means every action is both auditable and constrained by the safety filter. Skills are registered in `skills/registry.py` with JSON-schema parameters so the LLM can see them in its prompt.

## 4. Running the System

### Prerequisites

- Docker + Docker Compose
- Linux host with an NVIDIA K80 (or any CUDA 3.7+ GPU with ≥8 GB VRAM per model instance)
- Gemma 4 E2B or E4B GGUF weights downloaded to `inference/models/`
- `.env` file with `BATTLEGROUND_PASSWORD=<password>` (never hardcoded)

### Start a Game

```bash
# 1. Start KoboldCpp on the host (K80 GPU)
bash inference/start_koboldcpp.sh

# 2. Start the stack
./scripts/reset.sh        # tears down, rebuilds, health-waits
./scripts/start.sh        # brings services up cleanly
```

### Observe

```bash
python -m display.dashboard        # live 3-column terminal HUD
python -m display.replay --speed 2 # post-game replay from decision log
```

The dashboard polls `/game/status` and `/decisions/{role}` and renders a red panel, centered scoreboard, and blue panel using Rich. The replay viewer reads the full decision log from SQLite and replays each decision with timestamp-proportional delay.

## 5. Scoring

Scoring has two independent layers. The **decision log** (`data/decisions.jsonl` + SQLite `decision_log` table) records every reasoning trace, command, exit code, and safety verdict — this is the AI-reasoning showcase. The **competitive score** is point-based:

| Event                         | Points |
| ----------------------------- | ------ |
| Red: successful recon step    | 5      |
| Red: exploited service        | 15     |
| Red: privilege escalation     | 20     |
| Red: persistence installed    | 15     |
| Red: undetected action bonus  | 5      |
| Blue: service hardened        | 10     |
| Blue: intrusion detected      | 15     |
| Blue: threat neutralized      | 20     |
| Blue: stealth action caught   | 5      |
| Blue: uptime maintained/turn  | 1      |

**Win conditions:** time expiry, red full kill chain complete, blue lockout of red, or critical service down. A human-readable narrative (`generate_narrative`) summarizes the winner, duration, key moments, kill-chain progress, and decisive reasoning quotes.

## 6. Safety Model

All command execution funnels through `orchestrator/safety_filter.validate_command` before touching the battleground. The filter blocks 14 always-deny patterns (including `rm -rf /`, fork bombs, `mkfs`, outbound SSH to non-battleground IPs) and applies role-based restrictions: blue cannot install attacker tools, red cannot stop the orchestrator agent's SSH account. Blocked commands are logged to the `safety_log` table with the reason; allowed commands proceed to `ssh_executor.execute_command`. The battleground password is read only from the `BATTLEGROUND_PASSWORD` environment variable — any attempt to start the orchestrator without it raises `ValueError` at import.

## 7. Project Status & Known Gaps

Phase 1 (foundation), Phase 2 (agents + game), and Phase 3 (demo readiness) are all structurally complete (24/27 requirements satisfied in code; 3 require hardware runtime). A v1 milestone audit (`.planning/v1-MILESTONE-AUDIT.md`) identified three cross-phase integration blockers and three data-contract breaks that prevent the canonical demo flow from running end-to-end without fixes:

1. `game/loop.run_game` is orphaned — no script invokes it
2. Two execution models coexist (autonomous agent containers vs orchestrator-driven loop)
3. Agent containers lack a route to the inference server
4. Scoring maps reference stale skill names
5. Per-turn agent graphs reset state
6. Blue skills leak `orchestrator_url` into the LLM parameter surface

Phases 4–6 (execution model consolidation, scoring contract fixes, live runtime validation) are planned to close these before capstone presentation.

## 8. Repository Layout

```
.planning/          GSD workflow: project, requirements, roadmap, phase plans, audit
agents/             base_agent.py (LangGraph) + red_agent/ + blue_agent/
skills/             registry.py + red/ + blue/ — all real shell-command wrappers
orchestrator/       FastAPI + safety_filter + ssh_executor + db (SQLite) + game endpoints
game/               loop, state machine, scoring engine, narrative generator, snapshots
inference/          KoboldCpp launcher + test_inference.py (GPU validation)
display/            Rich dashboard, replay viewer, shared components
presentation/       Capstone slides (Marp) + Mermaid architecture diagram
scripts/            reset.sh, start.sh, test-network-isolation.sh
tests/              pytest suites for game engine, act_node parsing, scoring
docker-compose.yml  4 services, 3 isolated networks
```

---

*Last updated: 2026-04-10*
