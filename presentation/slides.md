---
marp: true
theme: default
paginate: true
---

# CyberSec AI Capstone
## Red vs Blue Autonomous Warfare

**Name:** [Your Name]
**Date:** April 2026
**Course:** Cybersecurity Capstone

---

# The Problem

### Can AI agents attack and defend a live system autonomously?

- Real commands on real infrastructure — no simulations
- Agents observe system state, reason about it, and act
- No human guidance during the game
- Both sides run simultaneously in isolated containers

**Goal:** Prove that LLM-driven agents can make meaningful cybersecurity decisions independently.

---

# Architecture

### Hub-and-Spoke Design

```
red-agent ──┐
             ├──► Orchestrator ──► Safety Filter ──► battleground (Ubuntu)
blue-agent ─┘         │
                       └──► SQLite (scores + events)
```

- **4 containers:** red-agent, blue-agent, battleground, orchestrator (FastAPI)
- **KoboldCpp** on host GPU serving Gemma 4 E4B
- **3 isolated networks:** red-net, blue-net, orchestrator-net
- **Key constraint:** agents never communicate directly — all traffic through orchestrator

---

# Agent Design

### LangGraph Observe → Reason → Act Loop

1. **Observe** — query `/state` endpoint, receive current system snapshot
2. **Reason** — send state + history to Gemma 4 via KoboldCpp, get JSON action
3. **Act** — POST skill name + args to `/execute`, receive output + score update
4. Repeat

**LLM:** Gemma 4 E4B Q4_K_M via KoboldCpp (OpenAI-compatible API, port 5001)
**Inference:** Sequential — one agent at a time, max 2048 input + 512 output tokens
**Robustness:** Regex fallback parser, 3-retry with format hints, rolling context window
**Memory:** Long-term JSON memory file + JSONL decision log per agent

---

# Red Team Skills

| Skill | Category | Description |
|-------|----------|-------------|
| `recon` | Recon | Network scan, enumerate open ports and services |
| `enum_users` | Recon | List system users, check for weak accounts |
| `find_vulns` | Recon | Search for known vulnerable service versions |
| `exploit_service` | Exploit | Attempt exploit against a discovered service |
| `brute_force` | Exploit | Credential brute-force against SSH or web login |
| `privesc` | PrivEsc | Attempt privilege escalation via SUID/sudo misconfigs |
| `install_persistence` | Persistence | Plant backdoor (cron job, authorized_keys) |
| `exfil_data` | Persistence | Attempt to read/copy sensitive files |

**8 skills total.** Agents pick by name — no raw shell access.

---

# Blue Team Skills

| Skill | Category | Description |
|-------|----------|-------------|
| `harden_ssh` | Hardening | Disable root login, enforce key-only auth |
| `patch_service` | Hardening | Update or reconfigure vulnerable service |
| `close_port` | Hardening | Firewall off unnecessary ports |
| `check_auth_log` | Detection | Parse auth.log for failed login attempts |
| `detect_backdoors` | Detection | Scan cron, authorized_keys, SUID files |
| `monitor_processes` | Detection | List unexpected running processes |
| `block_ip` | Response | Add iptables DROP rule for attacker IP |
| `kill_process` | Response | Terminate suspicious process by PID |
| `restore_service` | Uptime | Restart a service the red agent stopped |
| `check_services_up` | Uptime | Verify all expected services are running |

**10 skills total.**

---

# Scoring System

### Point Values

| Event | Points | Team |
|-------|--------|------|
| `recon_complete` | 5 | Red |
| `service_exploited` | 15 | Red |
| `privesc_achieved` | 20 | Red |
| `persistence_installed` | 20 | Red |
| `full_kill_chain` | **+40 bonus** | Red |
| `vuln_patched` | 10 | Blue |
| `attack_detected` | 10 | Blue |
| `attacker_blocked` | 15 | Blue |
| `service_kept_up` | 5 | Blue |
| `lockout_achieved` | **+40 bonus** | Blue |

### AI Quality Bonuses (both teams)
`red_undetected_action` +5 · `blue_detected_stealthily` +5 · `pivot_on_failure` +3 · `correct_inference` +3 · `adaptive_escalation` +5

---

# Game Flow

### Three Phases

```
Setup Phase (2–5 min)
  Blue agent hardens the battleground
  Patches services, closes ports, configures SSH
  Red agent is idle

Battle Phase (simultaneous, time-limited)
  Both agents run their observe → reason → act loops
  Sequential inference: one LLM call at a time
  Scores accumulate in real time

Conclusion
  Scoring engine finalizes totals
  Narrative generator summarises key events
  Winner declared: highest score wins
```

**Display:** Rich terminal dashboard shows live scores, last action, turn count, and game log.

---

# Live Demo

## Let's Watch a Game

```bash
./scripts/start_game.sh
```

- Orchestrator starts on port 8000
- Battleground container launches with vulnerable services
- Blue agent hardens during setup phase
- Battle begins — watch both agents reason and act in real time

**What to watch for:**
- Red agent discovering and exploiting a vulnerability
- Blue agent detecting the intrusion and blocking
- Full kill chain bonus triggering

---

# Results & Lessons Learned

### Post-Demo Discussion

*(To be filled in after the live demo)*

**Questions to address:**
- Which agent won and why?
- Did Gemma 4 produce coherent reasoning in its action choices?
- Where did the agents surprise us?
- What would improve agent decision quality?
- Real-world applicability: where does this approach break down?

---

# Questions?

### Repository

```
/agents/        — LangGraph agent loops (red + blue)
/skills/        — Red (8) and blue (10) skill modules
/game/          — Scoring engine, game loop, narrative
/orchestrator/  — FastAPI hub, safety filter, SSH proxy
/presentation/  — These slides + architecture diagram
```

**Architecture diagram:** `presentation/architecture.md`

**Run the demo:** `./scripts/start_game.sh`
