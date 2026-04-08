# Feature Landscape: Autonomous Cybersecurity Agent Simulation

**Domain:** Autonomous red/blue team AI agent simulation over a live VM
**Researched:** 2026-04-08
**Confidence:** MEDIUM-HIGH (WebSearch cross-referenced with multiple sources; no single canonical spec exists for this exact format)

---

## Table Stakes

Features that must exist or the simulation fundamentally does not work. Missing any of these = broken product.

### Agent Capabilities

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Shell command execution (nmap, metasploit, iptables, etc.) | Core mechanic — agents must act in the real environment | Medium | Subprocess wrapper with timeout + output capture. Needs kill switch. |
| Tool output parsing and interpretation | Agent must understand what commands returned to decide next action | Medium | LLM prompt must include structured output context; raw stdout is unreliable |
| Sequential reasoning loop (observe → plan → act → reflect) | Without this, agents fire commands randomly with no strategy | Medium | ReAct-style loop: current state + tool output → next action |
| Working memory / context window management | K80 with 24GB VRAM and Gemma 4 will hit context limits fast | High | Sliding window or summarization is mandatory; context overflow = agent brain-death |
| Action validity checking before execution | Prevents agent from issuing malformed/destructive commands to the host | Medium | Allowlist of permitted tools; parse command before exec |
| Agent termination and timeout handling | Agents will hang on blocking commands or infinite loops | Low-Medium | Per-command timeout; max total turn budget |

### Game Mechanics

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Phase sequencing (setup → battle → scoring) | Defines the game structure; without it there is no match | Low | State machine: BLUE_SETUP → BATTLE → SCORING |
| Phase timers / turn limits | Unbounded battle phase makes the simulation unpresentable | Low | Wall-clock timer or action-count limit per phase |
| Blue setup phase (firewall rules, services, hardening) | Blue team needs prep time before attacker starts; otherwise it's not a contest | Medium | Blue executes hardening commands on VM before red agent spawns |
| Simultaneous or alternating battle turns | Core adversarial mechanic | Medium | True simultaneous is hard; alternating turns with logging is presentable and correct |
| Win/loss condition detection | Defines when the simulation ends | Medium | Red wins: root shell obtained or flag captured. Blue wins: red locked out by deadline. |
| VM state isolation between runs | Replayability requires clean state | High | Snapshot/restore via VirtualBox/KVM or Docker container reset |

### Scoring

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Action log (what each agent did, in order) | Minimum audit trail for presentation | Low | Append-only log file per agent per run |
| Decision log (why each agent acted — reasoning trace) | The AI reasoning dimension; this is what differentiates from scripted tools | Medium | Capture the LLM's chain-of-thought or at minimum its stated plan before each action |
| Points-based scoring for key events | Makes the outcome legible to a non-technical audience | Medium | +points for red: recon hit, vuln exploited, privilege escalated, flag captured. +points for blue: blocked scan, patched service, detected intrusion, maintained uptime. |
| Final score summary per run | Required for the capstone presentation's conclusion | Low | Rendered at end of SCORING phase from accumulated points |

### Safety

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Command allowlist / denylist | Without it, an agent could destroy the host OS | Medium | Denylist: `rm -rf /`, `shutdown`, `reboot`, host-network-modifying commands outside the VM |
| Agent sandbox boundary enforcement | Agents must not escape the VM to the host | High | All agent commands execute inside the VM only; orchestrator runs outside with strict separation |
| Emergency kill switch | Manual override to halt both agents mid-run | Low | SIGTERM handler + clean shutdown; keyboard interrupt or API endpoint |
| Rate limiting on command execution | Prevents runaway agents from exhausting GPU/CPU | Low | Max N commands per second per agent |

---

## Differentiators

Features that make this capstone stand out. None of these are required for basic function, but they elevate the project from "it works" to "impressive."

### Agent Intelligence

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Persistent memory across turns (skill accumulation) | Agent improves within a match — discovers a vuln in turn 2, exploits in turn 7 | Medium | Simple: append successful actions to a "learned this run" context block. Advanced: vector store. |
| Red agent attack chaining (recon → exploit → escalate) | Demonstrates multi-step autonomous reasoning, not just one-shot tool calls | High | Requires the agent to maintain a goal hierarchy and track partial progress |
| Blue agent adaptive response (detects pattern, changes defense) | Blue isn't just running static rules — it reacts to observed red behavior | High | Blue's decision loop must include analysis of its own logs + red's visible actions |
| Agent "persona" constraints (red acts like an APT, blue acts like a SOC) | Gives the simulation narrative coherence; impressive for presentation | Low | System prompt framing; minimal implementation cost for high presentation value |
| Self-assessment / reflection step | Agent evaluates whether its last action worked before choosing the next | Medium | Add a reflection token after each action: "Did this work? Evidence:" |

### Game Mechanics

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Multiple scenario configurations | Swap in different VM vulnerability profiles for varied runs | Medium | Config-driven: scenario YAML defines open ports, vulns, flag locations |
| Honeypot deployment by blue team | Blue can plant fake credentials or services to waste red's turns | Medium | High presentation value; demonstrates real defensive deception technique |
| Lateral movement simulation (multiple VM nodes) | More realistic; red must pivot, blue must segment | Very High | Out of scope for K80 single-VM capstone — defer entirely |
| Difficulty tiers (easy/medium/hard VM configs) | Lets presenters dial the match for audience | Low | Just different scenario YAMLs; pre-configure 2-3 before presentation |

### Observability and Presentation

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Live dashboard (terminal or web) showing both agents' actions in real time | Hugely impressive for capstone; audience sees the battle as it happens | High | curses TUI or simple Flask SSE stream; do not underestimate this complexity |
| Replay mode (re-execute a recorded session) | Can present the same interesting run multiple times without re-running the model | Medium | Log all commands + timestamps; replay driver re-executes them with delays |
| Side-by-side reasoning trace display | Show what both agents were "thinking" — the AI reasoning dimension made visible | Medium | Pull decision log per turn, format it in two columns for presentation |
| Run comparison (this run vs. baseline) | Shows improvement or variation across runs | High | Nice to have; low priority for capstone |
| Exportable report (PDF or HTML) | Leave-behind artifact for professors/judges | Medium | Generate from the action log + decision log + final score |

### Scoring Extensions

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Weighted scoring by technique sophistication | Rewards clever attacks/defenses, not just successful ones | Medium | Assign multipliers: basic scan = 1x, chained exploit = 3x, stealth evasion = 2x |
| MITRE ATT&CK technique tagging on actions | Maps agent actions to real-world threat framework; academic credibility | High | LLM classification of each action into ATT&CK tactic/technique post-hoc |
| Blue team detection rate metric | How many red actions did blue catch? Separate from win/loss | Medium | Track blue's log analysis hits vs. red's total actions |

---

## Anti-Features

Things to deliberately NOT build. Common mistakes in this domain.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Scripted agent actions | If agents follow a hardcoded attack/defense script, the AI dimension is gone — it's just a demo, not a simulation | Let the LLM choose every action from tool descriptions; resist hardcoding "step 1 = nmap" |
| Real internet-facing VM | Agents executing real exploits on a public host is legally and ethically problematic | Isolated local VM only (VirtualBox or KVM on the K80 host); no external network connectivity |
| Shared context between agents | If red can read blue's memory (or vice versa), the adversarial mechanic collapses | Strict process/context isolation; agents communicate only through the VM's observable state |
| Unbounded context accumulation | On a K80 with Gemma 4, filling context = OOM or severely degraded generation quality | Implement context pruning from day one; design for 2-4k token working window |
| Multi-turn human-in-the-loop approval | Stops the "autonomous" claim; breaks pacing for presentation | Emergency kill switch only; no per-action approval |
| RL training during the demo | Training Gemma 4 live on 24GB VRAM is not feasible and adds enormous complexity | Use inference only; the LLM is pre-trained; the "learning" is in-context memory, not weight updates |
| Full network topology simulation | Multi-node lateral movement is technically interesting but out of scope for this hardware and timeline | One VM, rich vulnerability profile, focused scenario |
| Real CVE exploitation on unpatched software | Metasploit modules against real unpatched CVEs on a live VM can be unpredictable and hard to reset | Use intentionally vulnerable VM images (Metasploitable, DVWA, VulnHub); known, resettable state |
| Streaming output without buffering | Raw LLM streaming into shell execution is a race condition | Buffer full LLM response → parse → validate → execute; never pipe LLM tokens directly to shell |

---

## Feature Dependencies

```
VM Snapshot/Reset
  └── Phase Sequencing (reset between runs enables replayability)
       └── Phase Timers
            └── Win/Loss Detection
                 └── Final Score Summary

Command Allowlist
  └── Shell Execution
       └── Tool Output Parsing
            └── Sequential Reasoning Loop
                 ├── Working Memory Management
                 ├── Action Log
                 └── Decision Log (reasoning trace)
                      └── Side-by-side Reasoning Display (differentiator)
                           └── Replay Mode (differentiator)

Blue Setup Phase
  └── Simultaneous/Alternating Battle
       ├── Red: Attack Chaining (differentiator)
       └── Blue: Adaptive Response (differentiator)
            └── Honeypot Deployment (differentiator)

Points Scoring
  └── Weighted Scoring (differentiator)
       └── MITRE ATT&CK Tagging (differentiator)
```

Key dependency constraint: VM snapshot/restore is a prerequisite for replayability. If this is hard to implement cleanly on the K80 host, use Docker containers with a known vulnerable image as the simpler alternative.

---

## MVP Recommendation

For a functional capstone demo, prioritize in this order:

**Phase 1 — Core loop:**
1. Shell execution with allowlist + timeout
2. Sequential reasoning loop (observe → plan → act)
3. Working memory management (sliding context window)
4. Action log + decision log
5. Phase state machine (setup → battle → scoring)
6. Phase timers + win/loss detection
7. Points scoring + final summary

**Phase 2 — Differentiation:**
8. VM snapshot/reset for replayability
9. Agent persona framing (system prompt APT/SOC)
10. Side-by-side decision log display for presentation
11. Replay mode

**Defer to post-MVP (if time allows):**
- Live dashboard (high complexity, high reward — do it only if Phase 1+2 are solid)
- MITRE ATT&CK tagging (impressive but non-functional for the simulation itself)
- Honeypot deployment (medium complexity, good story — second-priority differentiator)
- Weighted scoring multipliers
- Multiple scenario configs

---

## Sources

- [Autonomous Red vs. Blue Teaming — ISACA 2026](https://www.isaca.org/resources/news-and-trends/industry-news/2026/autonomous-red-vs-blue-teaming-a-new-frontier-in-cybersecurity-risk-and-reward)
- [PentAGI — Autonomous Penetration Testing Agent (GitHub)](https://github.com/vxcontrol/pentagi)
- [A Survey of Agentic AI and Cybersecurity (arxiv)](https://arxiv.org/html/2601.05293v1)
- [CyberBattleSim — Microsoft (GitHub)](https://github.com/microsoft/CyberBattleSim)
- [HoneyAgents — AI-driven honeypot + autonomous agents (GitHub)](https://github.com/mrwadams/honeyagents)
- [Memory for Autonomous LLM Agents (arxiv)](https://arxiv.org/html/2603.07670)
- [Agentic Purple Teaming — Lasso Security](https://www.lasso.security/blog/lasso-agentic-purple-teaming)
- [Forewarned is Forearmed: LLM-based Agents in Autonomous Cyberattacks (arxiv)](https://arxiv.org/html/2505.12786v2)
- [Deep Reinforcement Learning for Autonomous Cyber Operations: A Survey (arxiv)](https://arxiv.org/html/2310.07745v2)
- [Smarter Honeypots with GenAI (royans.net)](https://royans.net/security/honeypot/genai/2025/12/28/Smarter-honeypots-using-GenAI-v2.html)
