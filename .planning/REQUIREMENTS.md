# Requirements: CyberSec AI Capstone

**Defined:** 2026-04-08
**Core Value:** Autonomous AI agents that reason about cybersecurity decisions and execute real commands on real infrastructure

## v1 Requirements

### Infrastructure

- [ ] **INFRA-01**: Docker Compose setup with 3 containers (red-agent, blue-agent, battleground) on isolated networks
- [ ] **INFRA-02**: KoboldCpp running Gemma 4 (e2b or e4b) on K80 GPU serving both agents via OpenAI-compatible API
- [ ] **INFRA-03**: SSH-based command execution from agents to battleground via orchestrator safety filter
- [ ] **INFRA-04**: One-command game reset that returns all containers to fresh state
- [ ] **INFRA-05**: Agent safety filter — orchestrator validates/sanitizes commands before execution (prevents container escape)

### Agent Core

- [ ] **AGNT-01**: Autonomous reasoning loop (observe → reason → act → observe) powered by Gemma 4
- [ ] **AGNT-02**: Tool/skill system with defined cybersecurity tools agents can invoke
- [ ] **AGNT-03**: Short-term memory (rolling context window) + long-term memory (key findings JSON)
- [ ] **AGNT-04**: Decision logging capturing every action with reasoning trace
- [ ] **AGNT-05**: Turn limit and command deduplication to prevent infinite retry loops

### Red Team

- [ ] **RED-01**: Reconnaissance skills (port scanning, service enumeration)
- [ ] **RED-02**: Exploitation skills (service exploits, credential attacks)
- [ ] **RED-03**: Privilege escalation skills
- [ ] **RED-04**: Persistence skills (backdoor users, cron jobs, SSH keys)

### Blue Team

- [ ] **BLUE-01**: Hardening skills (firewall rules, service config, user lockdown)
- [ ] **BLUE-02**: Detection skills (log monitoring, process watching, connection tracking)
- [ ] **BLUE-03**: Response skills (kill processes, remove unauthorized users, block IPs)
- [ ] **BLUE-04**: Uptime maintenance (service health checks, restoration)

### Game Mechanics

- [ ] **GAME-01**: Phase-based flow — blue setup phase (2-5 min) → simultaneous battle → conclusion
- [ ] **GAME-02**: Two-layer scoring — decision log (AI reasoning showcase) + competitive points
- [ ] **GAME-03**: Battleground state snapshots every 30-60 seconds
- [ ] **GAME-04**: Win conditions — time expiry, red full kill chain, or blue lockout
- [ ] **GAME-05**: Detection/stealth bonuses — blue scores for catching stealthy actions, red scores for evasion

### Presentation

- [ ] **PRES-01**: Rich terminal display showing real-time game progress
- [ ] **PRES-02**: Capstone presentation slides with architecture diagram
- [ ] **PRES-03**: Post-game log/replay viewer
- [ ] **PRES-04**: Architecture diagram for slides

## v2 Requirements

### Advanced Agent

- **AGNT-V2-01**: Adaptive strategy — agents learn from opponent behavior mid-game
- **AGNT-V2-02**: Agent personas — different attack/defense styles (aggressive, stealthy, methodical)

### Advanced Game

- **GAME-V2-01**: Multiple battleground VMs (multi-node scenarios)
- **GAME-V2-02**: Web dashboard with live visualization
- **GAME-V2-03**: Tournament mode — multiple rounds with cumulative scoring

### Advanced Infrastructure

- **INFRA-V2-01**: Second K80 GPU for dedicated per-agent inference
- **INFRA-V2-02**: Honeypot deployment by blue team

## Out of Scope

| Feature | Reason |
|---------|--------|
| Human-in-the-loop during gameplay | Agents must be fully autonomous |
| Web UI dashboard | Terminal output sufficient for capstone; v2 candidate |
| Network-level attacks between VMs | Attacks happen on battleground only |
| Model training/fine-tuning | Using Gemma 4 out of the box via KoboldCpp |
| Cloud API inference | All local on K80 GPU |
| Multi-battleground scenarios | Single Ubuntu VM target for v1 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Pending |
| INFRA-02 | Phase 1 | Pending |
| INFRA-03 | Phase 1 | Pending |
| INFRA-04 | Phase 3 | Pending |
| INFRA-05 | Phase 1 | Pending |
| AGNT-01 | Phase 1 | Pending |
| AGNT-02 | Phase 2 | Pending |
| AGNT-03 | Phase 1 | Pending |
| AGNT-04 | Phase 1 | Pending |
| AGNT-05 | Phase 1 | Pending |
| RED-01 | Phase 2 | Pending |
| RED-02 | Phase 2 | Pending |
| RED-03 | Phase 2 | Pending |
| RED-04 | Phase 2 | Pending |
| BLUE-01 | Phase 2 | Pending |
| BLUE-02 | Phase 2 | Pending |
| BLUE-03 | Phase 2 | Pending |
| BLUE-04 | Phase 2 | Pending |
| GAME-01 | Phase 2 | Pending |
| GAME-02 | Phase 2 | Pending |
| GAME-03 | Phase 2 | Pending |
| GAME-04 | Phase 2 | Pending |
| GAME-05 | Phase 2 | Pending |
| PRES-01 | Phase 3 | Pending |
| PRES-02 | Phase 3 | Pending |
| PRES-03 | Phase 3 | Pending |
| PRES-04 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0

---
*Requirements defined: 2026-04-08*
*Last updated: 2026-04-08 — traceability updated with phase mappings*
