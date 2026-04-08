# CyberSec AI Capstone — Red vs Blue Autonomous Warfare

## What This Is

An AI-driven cybersecurity simulation where two autonomous agents — a red team attacker and a blue team defender — compete over a live Ubuntu battleground VM using real commands and real tools. Agents are powered by Gemma 4 (e2b or e4b) running on a 24GB K80 GPU via Kobalt, and make their own decisions about what to execute, when, and why. The system is replayable and designed for live presentation.

## Core Value

Autonomous AI agents that reason about cybersecurity decisions and execute real commands on real infrastructure — proving AI can independently attack and defend systems without human guidance.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Red agent autonomously discovers and exploits vulnerabilities on a fresh Ubuntu VM using real shell commands
- [ ] Blue agent autonomously hardens and defends the Ubuntu VM using real shell commands
- [ ] Both agents run Gemma 4 (e2b or e4b) on a 24GB K80 GPU via Kobalt
- [ ] Agents manage their own skills, memory, and context independently
- [ ] Game follows phase structure: blue setup → simultaneous battle → scored conclusion
- [ ] Blue setup phase (2-5 min) where blue agent autonomously hardens the VM
- [ ] Battle phase where both agents operate simultaneously in real time
- [ ] Scoring snapshots every 30-60 seconds during battle phase
- [ ] Game ends on: time expiry, red full kill chain, or blue lockout of red
- [ ] Two-layer scoring: decision log (AI reasoning showcase) + competitive points
- [ ] Red scores for: recon, access, privilege escalation, persistence, exfiltration
- [ ] Blue scores for: hardening, detection, blocking, response, uptime maintenance
- [ ] Detection bonuses (blue detects stealthy red action) and stealth bonuses (red evades blue)
- [ ] 3-VM architecture: red agent VM, blue agent VM, battleground VM
- [ ] Docker-based infrastructure for replayability
- [ ] Full decision log capturing what each agent did and why
- [ ] System is replayable — start a new game with one command
- [ ] Presentation slides for capstone demo

### Out of Scope

- Human-in-the-loop during gameplay — agents are fully autonomous once started
- Web UI dashboard — terminal/log output is sufficient for capstone
- Multi-battleground scenarios — single Ubuntu VM target
- Training or fine-tuning models — using Gemma 4 out of the box via Kobalt
- Network-level attacks between VMs — attacks happen on the battleground only

## Context

- This is a mini capstone project for a cybersecurity program
- The server hosting this has 2x K80 GPUs (one potentially needs reseating, one confirmed working at 24GB)
- Kobalt is the inference runtime (not Ollama)
- Gemma 4 e2b (~2B params) or e4b (~4B params) — both fit on 24GB, e4b is smarter but heavier
- Two model instances need to run simultaneously on the single working K80
- The battleground VM starts as a fresh Ubuntu install each game — no pre-planted vulnerabilities, blue hardens it, red finds what blue missed
- Turn structure is phase-based with simultaneous play during battle phase
- Must be demo-able in a presentation setting — replayable and visually clear from logs

## Constraints

- **Hardware**: Single working 24GB K80 GPU must run both agent models simultaneously
- **Model**: Gemma 4 via Kobalt — no cloud APIs, all local inference
- **Infrastructure**: Docker-based VMs for reproducibility
- **Timeline**: Capstone project — needs to be presentable
- **Scope**: Single battleground VM, no multi-node scenarios
- **Autonomy**: Agents must reason and act independently — no scripted playbooks

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Kobalt over Ollama | Server-specific runtime choice for K80 | — Pending |
| Gemma 4 (e2b vs e4b) | Must fit 2 instances on 24GB K80 | — Pending |
| Phase-based with simultaneous battle | Realistic attack/defense dynamics, better demo | — Pending |
| Two-layer scoring (decision log + points) | Showcases AI reasoning AND provides competitive game | — Pending |
| Fresh Ubuntu battleground (no pre-planted vulns) | Blue hardens, red finds gaps — more realistic | — Pending |
| Docker-based VMs | Replayability for presentations | — Pending |

---
*Last updated: 2026-04-08 after initialization*
