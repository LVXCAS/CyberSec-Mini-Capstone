# Phase 1: Foundation - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Infrastructure and orchestrator are running and proven safe — agents can execute commands on the battleground through a validated safety layer. Includes Docker Compose setup, KoboldCpp on K80 GPU, SSH command execution via orchestrator, safety filter, and a single autonomous agent loop with memory and decision logging.

</domain>

<decisions>
## Implementation Decisions

### Safety filter design
- Blocklist approach — everything runs except dangerous command patterns (rm -rf, reboot, docker escape, etc.)
- Blocked commands visible in demo — a separate "safety filter activations" panel/log showing what was caught
- Rejection behavior and blocklist storage (hardcoded vs config file): Claude's discretion

### Agent reasoning loop
- Observations include command output PLUS system state snapshot (open ports, processes, etc.) — Claude has discretion on exactly what state given VRAM constraints
- Decision log uses both layers: full LLM reasoning in a verbose log + structured summary (intent, command, result, outcome) in the game log
- Turn limit: between 10-20 turns, Claude's discretion on exact number (adjustable in Phase 2)
- Failed command handling: Claude's discretion

### Container & network layout
- Agents are unaware they're in containers — they see the battleground as a remote server on the network
- Battleground is a realistic server: Ubuntu with web app, database, cron jobs, multiple users, log files
- Agent containers have their own toolkits pre-installed (nmap on red, auditd/monitoring on blue) — not just thin orchestrator clients
- Network isolation approach (separate Docker networks vs same network with filtering): Claude's discretion, must satisfy INFRA-01

### KoboldCpp fallback strategy
- Must run locally on K80 — no cloud GPU fallback, local-only inference is part of the capstone narrative
- If E4B too large for 24GB VRAM, drop to Gemma 4 E2B (stay with Gemma 4 family)
- CUDA 3.7 fallback and inference backend choice: Claude's discretion (build from source, CPU fallback, or llama.cpp — whatever works fastest)
- Inference timeout: Claude's discretion, balancing demo watchability with reasoning quality

### Claude's Discretion
- Safety filter: rejection response format, blocklist storage method (hardcoded vs config)
- Agent loop: exact system state included in observations, failed command handling, turn limit (10-20 range)
- Containers: network isolation implementation approach
- Inference: CUDA 3.7 fallback path, inference timeout threshold

</decisions>

<specifics>
## Specific Ideas

- Safety filter activations should be demo-visible — showcases the safety layer to capstone audience
- Agents should believe they're on a real network, not in containers — immersion matters for the narrative
- Battleground should feel like a real production server, not a bare VM
- Both verbose reasoning log and structured game log — verbose for AI showcase, structured for replay

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-04-08*
