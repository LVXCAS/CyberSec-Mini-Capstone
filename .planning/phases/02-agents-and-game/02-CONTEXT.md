# Phase 2: Agents and Game - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Both agents execute real cybersecurity skills autonomously and a complete game runs from blue setup through simultaneous battle to a scored conclusion. Creating posts, demo polish, terminal display, and replay are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Skill design
- Granularity: Claude's discretion — pick what works best with Gemma 4's reasoning capabilities
- Real tools installed in containers (nmap, hydra, etc.) — not simplified wrappers
- Battleground has both system-level vulns (weak SSH passwords, SUID binaries, misconfigured services) AND a vulnerable web app (SQL injection, file upload, default creds)
- Blue detection approach: Claude's discretion — active polling or event-driven, based on what Gemma 4 can reason about effectively

### Game flow & timing
- Blue setup phase: 5 minutes before red begins attacking
- Battle phase: simultaneous with queue — both agents submit actions concurrently, orchestrator processes sequentially
- Total battle duration: 20 minutes
- Early termination triggers (all active):
  - Red full kill chain (recon + exploit + privesc + persistence) — red victory
  - Blue lockout (all attack paths blocked) — blue victory
  - Critical service down for 2+ minutes — penalty/game-over
  - Early termination on red breach

### Scoring & win conditions
- Two-layer scoring with equal weight: competitive points AND AI reasoning showcase displayed together
- Stealth/detection bonuses: Claude's discretion — design the mechanic based on what's demonstrable
- Point categories: Claude's discretion — design a scoring system that reads well on terminal display
- Final score summary: narrative format — tells the story of the game with key moments highlighted, points shown inline (not a table)

### Agent behavior tuning
- Red agent: adaptive — starts methodical (thorough recon, careful exploitation), escalates aggression if running out of time
- Agent reasoning displayed in real-time on terminal — audience sees the AI "thinking" live (compelling for capstone demo)
- Fog of war — each agent only sees the battleground state, must discover what the other did
- On failure: agent reasons about why it failed and pivots strategy (best AI showcase)

### Claude's Discretion
- Skill granularity (atomic vs multi-step recipes)
- Blue detection mechanism (polling vs event-driven)
- Stealth/detection bonus mechanic design
- Scoring point categories and values
- Exact prompt engineering for agent personas

</decisions>

<specifics>
## Specific Ideas

- Real-time reasoning display is a key capstone differentiator — audience should see agents "thinking"
- Narrative game summary should read like a story: "Red breached the system in 12:34, achieving privilege escalation before blue could detect the initial exploit. Key moment: Red's SSH brute force succeeded on turn 7 while blue was focused on firewall hardening."
- Adaptive red agent behavior mirrors real attacker behavior — methodical recon first, then escalation under time pressure
- Fog of war forces agents to demonstrate actual detection/investigation skills rather than reacting to known actions

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-agents-and-game*
*Context gathered: 2026-04-08*
