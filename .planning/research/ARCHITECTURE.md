# Architecture Patterns: Autonomous Red vs Blue AI Simulation

**Domain:** Multi-VM autonomous cybersecurity agent simulation
**Researched:** 2026-04-08
**Overall confidence:** HIGH (component structure), MEDIUM (Kobalt-specific integration)

---

## Recommended Architecture

Three physically distinct VMs with a central orchestrator process. All runtime traffic routes through the orchestrator — agents never communicate directly with each other, and never receive unsanitized output that could influence the battleground VM outside their intended execution path.

```
┌─────────────────────────────────────────────────────────────────┐
│                       HOST MACHINE                              │
│                                                                 │
│  ┌──────────────────┐       ┌──────────────────┐               │
│  │   RED AGENT VM   │       │  BLUE AGENT VM   │               │
│  │                  │       │                  │               │
│  │  ┌────────────┐  │       │  ┌────────────┐  │               │
│  │  │  Agent     │  │       │  │  Agent     │  │               │
│  │  │  Process   │  │       │  │  Process   │  │               │
│  │  │  (Python)  │  │       │  │  (Python)  │  │               │
│  │  └─────┬──────┘  │       │  └─────┬──────┘  │               │
│  │        │REST     │       │        │REST      │               │
│  └────────┼─────────┘       └────────┼──────────┘               │
│           │                          │                           │
│           ▼                          ▼                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  ORCHESTRATOR PROCESS                    │   │
│  │                  (runs on host or dedicated VM)          │   │
│  │                                                          │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │   │
│  │  │ Phase State │  │ Scoring      │  │ Decision Log   │  │   │
│  │  │ Machine     │  │ Engine       │  │ Writer         │  │   │
│  │  └─────────────┘  └──────────────┘  └────────────────┘  │   │
│  │                                                          │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │         Command Relay + Safety Filter               │ │   │
│  │  └─────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │SSH (filtered)                      │
│                             ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   BATTLEGROUND VM                        │   │
│  │                   (Fresh Ubuntu each game)               │   │
│  │                                                          │   │
│  │   Red's actual effects + Blue's actual defenses          │   │
│  │   Snapshotted every 30-60s by Scoring Engine             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              KOBALT LLM INFERENCE SERVER                 │   │
│  │              (24GB K80, Gemma 4 e2b or e4b)              │   │
│  │              Shared by both agents via REST              │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Boundaries

### Component 1: Agent Process (Red / Blue, identical structure)

**Responsibility:** Autonomous decision loop. Perceives state, reasons via LLM, selects action, executes, stores result.

**Sub-components:**

| Sub-component | Purpose |
|---------------|---------|
| Perception Module | Receives observation payload from orchestrator (sanitized) |
| Planner (LLM call) | Sends prompt to Kobalt inference server, receives next action |
| Executor | Calls orchestrator's Command Relay API with the chosen command |
| Short-term Memory | Rolling window of recent observations (last N turns, in-context) |
| Long-term Memory | Structured JSON log of what was tried, outcome, status |
| Skill Registry | Curated list of commands/techniques the agent knows are available |

**Communicates with:**
- Kobalt inference server (outbound REST POST to `/api/chat` or `/v1/chat/completions`)
- Orchestrator Command Relay (outbound REST POST to submit command)
- Receives observation back from orchestrator (response to command POST or polling)

**Does NOT communicate with:**
- The other agent (ever)
- The battleground VM directly (all execution proxied through orchestrator)

---

### Component 2: Orchestrator

**Responsibility:** Game master. Controls phase transitions, routes commands to battleground, validates commands, triggers scoring, writes decision logs.

**Sub-components:**

| Sub-component | Purpose |
|---------------|---------|
| Phase State Machine | Manages: SETUP → BATTLE → CONCLUSION transitions |
| Command Relay | Receives command from agent, passes to battleground via SSH |
| Safety Filter | Blocks disallowed commands (see Safety Boundaries section) |
| Observation Builder | Reads battleground state, packages it for each agent |
| Scoring Engine | Snapshots battleground every 30-60s, computes scores |
| Decision Log Writer | Appends each agent action + reasoning to structured log file |
| End Condition Monitor | Checks: time expiry, red kill chain complete, blue lockout of red |

**Communicates with:**
- Both agent processes (receives command requests, sends observation responses)
- Battleground VM (SSH for command execution and state reads)
- Kobalt inference server (not directly — inference is agent-side)

---

### Component 3: Battleground VM

**Responsibility:** The real Ubuntu system where all effects land. Passively receives commands (relayed by orchestrator) and is read for state.

**What runs here:** Actual shell commands from both agents (via SSH from orchestrator).

**What does NOT run here:** Any agent logic, LLM inference, or orchestrator logic.

**Key property:** Fully replaceable. Each game starts from a Docker image snapshot. One command resets to fresh state.

---

### Component 4: Kobalt Inference Server

**Responsibility:** LLM inference for both agents. Serves Gemma 4 via REST API.

**Key constraint:** Single 24GB K80 must serve two agents. This means:
- Sequential token generation (one at a time, queued)
- Agents may experience latency while the other is generating
- Kobalt exposes an OpenAI-compatible endpoint: `/v1/chat/completions`

**Communicates with:** Both agent processes (inbound REST requests)

---

## Data Flow

### Phase: SETUP (Blue Only)

```
Blue Agent → POST /command {cmd, reasoning} → Orchestrator Safety Filter
  → SSH exec on Battleground VM
  → SSH read stdout/stderr
  → Orchestrator builds observation
  → POST response to Blue Agent with {observation, score_delta}
  → Blue Agent writes to Decision Log (via Orchestrator)
  → Repeat until setup time expires
```

### Phase: BATTLE (Simultaneous)

```
Both agents run their decision loops independently (async):

Red Agent:
  1. GET /observe → receives current battleground state slice
  2. Build prompt with memory + skills + observation
  3. POST /v1/chat/completions → Kobalt (blocks until LLM responds)
  4. Parse LLM output for chosen command
  5. POST /command {cmd, reasoning} → Orchestrator
  6. Receive observation response
  7. Update short-term + long-term memory
  8. Repeat

Blue Agent: (identical loop, different prompts and skill set)

Orchestrator (parallel, on tick):
  - Every 30-60s: snapshot battleground state → compute scores → append to score log
  - Each agent command: relay → execute → observe → respond
  - Each command: write entry to decision log
  - Check end conditions on every tick
```

### Phase: CONCLUSION

```
Orchestrator:
  - Sends GAME_OVER signal to both agents
  - Computes final scores from score log
  - Writes final summary to decision log
  - Outputs: score report, decision log JSON, replay metadata
```

---

## Communication Protocols

| Link | Protocol | Why |
|------|----------|-----|
| Agent → Orchestrator (commands) | REST HTTP POST | Simple, debuggable, language-agnostic |
| Agent → Kobalt (inference) | REST HTTP POST (OpenAI compat) | Kobalt exposes `/v1/chat/completions` |
| Orchestrator → Battleground | SSH (Paramiko in Python) | Standard remote execution, auditable |
| Agent → Orchestrator (observation) | REST HTTP GET or response body | Polling or synchronous response |
| Orchestrator → Agent (game signals) | REST response or event endpoint | Phase changes, game over signals |

**Why REST over message queues:** For a capstone project, REST is simpler to debug, requires no broker infrastructure, and provides natural request/response for the synchronous agent loop. A message queue (RabbitMQ, Kafka) would be warranted at scale but adds unnecessary complexity here.

**Why SSH to battleground (not Docker exec):** SSH is auditable, produces a natural log of every command, and maps to how real systems work — reinforcing the realistic nature of the simulation. Alternatively: `docker exec` into the battleground container works and is simpler if battleground is a container, not a VM.

---

## Safety Boundaries

The orchestrator's Safety Filter is the critical isolation layer. Agents never touch the battleground directly.

### Threat Model

| Threat | Mitigation |
|--------|------------|
| Agent generates command targeting orchestrator host | Safety filter: block commands with orchestrator/host IPs or hostnames |
| Agent generates command that attempts to escape Docker | Battleground VM is a full VM (not just container) — escape lands in VM, not host |
| Agent generates destructive command (rm -rf /) | Safety filter: blocklist of catastrophic commands |
| Agent attempts lateral movement to red/blue agent VMs | Safety filter: block all outbound network commands targeting non-battleground IPs |
| Agent exfiltrates data to external network | Battleground VM has no external internet route (firewall rule at host level) |
| Agent poisons its own memory | Memory is local to agent process — does not affect other agent or battleground |
| GPU memory contention (both agents generate simultaneously) | Kobalt queue handles serialization — acceptable latency for capstone demo |

### Safety Filter Implementation

```
Blocklist categories (Safety Filter checks each command before relay):
  - Commands targeting host filesystem: /proc/host, /var/run/docker.sock
  - Commands targeting non-battleground IPs: only battleground IP allowed
  - Catastrophic destructive commands: rm -rf /, dd if=/dev/zero, mkfs
  - Outbound network to external internet (curl/wget to non-local addresses)

Allowlist approach (stricter, recommended for demo):
  - Define a permitted command list per agent role
  - Red: nmap, hydra, ssh, curl, exploit tools, file read/write
  - Blue: ufw, iptables, fail2ban, systemctl, chmod, useradd, auditd
  - Everything else: blocked and logged
```

### Network Isolation

```
Host iptables rules:
  - Battleground VM → internet: BLOCKED
  - Red agent VM → Blue agent VM: BLOCKED
  - Red agent VM → Battleground VM: BLOCKED (only orchestrator can SSH to battleground)
  - Blue agent VM → Battleground VM: BLOCKED (same)
  - Both agent VMs → Kobalt inference server: ALLOWED (port 5001 or 11434)
  - Both agent VMs → Orchestrator API: ALLOWED (port 8080 or similar)
  - Orchestrator → Battleground: ALLOWED (SSH port 22)
```

---

## Suggested Build Order

Build order follows the dependency graph: each layer must exist before the next can be tested.

### Layer 1: Infrastructure (Foundation)

**What:** Docker Compose or VM setup with networking rules.
- Battleground VM: Ubuntu image, SSH configured, iptables rules in place
- Kobalt inference server running Gemma 4, reachable on REST
- Basic orchestrator skeleton (HTTP server, SSH client)

**Why first:** Nothing else can be tested without a place to run commands and a working LLM.

**Deliverable:** Can SSH from orchestrator to battleground. Can POST to Kobalt and get a text response.

---

### Layer 2: Orchestrator Core

**What:** Phase state machine + command relay (no scoring yet, no agents yet).
- Phase transitions: SETUP → BATTLE → CONCLUSION
- Command relay: receive POST from fake client, SSH to battleground, return output
- Safety filter: stub implementation (log but don't block yet)
- Decision log writer: append each command + response to JSONL file

**Why second:** The orchestrator is the central hub. Agents and scoring both depend on it working correctly.

**Deliverable:** Can send a test command via curl, see it execute on battleground, see it logged.

---

### Layer 3: Single Agent Loop (One Agent, Manual Control)

**What:** Agent process wired to real Kobalt + real orchestrator.
- Basic Planner-Executor loop (ReAct pattern: reason → act → observe)
- Prompt template that produces valid shell commands
- Short-term memory (rolling context window)
- Connects to Kobalt for LLM calls
- Connects to orchestrator to submit commands

**Why third:** Test the full LLM-to-execution path with one agent before adding the second. Most bugs live here.

**Deliverable:** Agent autonomously executes 3-5 commands on the battleground based on LLM reasoning.

---

### Layer 4: Scoring Engine

**What:** Battleground state snapshots + score computation.
- Snapshot script: reads key battleground indicators (open ports, running services, file presence, active users)
- Score computation: maps snapshot diff to point categories
- Score log: appends to JSONL on each snapshot

**Why fourth:** Scoring reads battleground state (layer 1 required) and integrates with orchestrator (layer 2 required). Agents (layer 3) produce the events scoring evaluates.

**Deliverable:** Scoring snapshots every 30s, produces readable score output.

---

### Layer 5: Both Agents + End Conditions

**What:** Red and blue agent processes running simultaneously.
- Second agent process (symmetric structure, different prompts/skills)
- Orchestrator handles interleaved command requests from both
- End condition monitor: time expiry, kill chain completion, blue lockout

**Why fifth:** Two-agent operation has coordination complexity (Kobalt queue contention, interleaved battleground state). Introduce only after single agent is solid.

**Deliverable:** Full game runs from start to scored conclusion.

---

### Layer 6: Replayability + Polish

**What:** Docker Compose one-command reset, decision log formatting, demo presentation.
- `docker compose down && docker compose up` resets battleground to fresh image
- Decision log formatted for readable terminal output
- Safety filter hardened (full blocklist/allowlist)
- README with demo instructions

**Why last:** Polish after correctness.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Agents with Direct Battleground Access

**What:** Agents SSH directly to the battleground VM, bypassing orchestrator.
**Why bad:** No safety filter, no decision logging, no scoring integration. An agent escape has no containment layer.
**Instead:** All execution proxied through orchestrator's Command Relay.

---

### Anti-Pattern 2: Agents Sharing In-Process Memory

**What:** Red and blue agent logic running in the same Python process, sharing memory.
**Why bad:** One agent can observe the other's internal state. Defeats the simulation's integrity.
**Instead:** Fully separate processes on separate VMs, no shared memory. Communication only through orchestrator's observation API.

---

### Anti-Pattern 3: Unlimited LLM Context

**What:** Feeding the full game history into every LLM call.
**Why bad:** Context fills up within ~10-20 turns on a 4B model. Performance degrades. Inference slows.
**Instead:** Rolling short-term window (last 5-10 observations) + structured long-term memory summary (key findings stored as JSON, not raw text).

---

### Anti-Pattern 4: Scoring from Agent Self-Reports

**What:** Agents report their own actions to the scoring engine.
**Why bad:** An agent can lie. Red could claim it achieved persistence without actually doing it.
**Instead:** Scoring engine reads battleground state independently via SSH. Ground truth comes from the system, not the agent.

---

### Anti-Pattern 5: Kobalt Called Synchronously in Tight Loop

**What:** Agent waits for LLM response before doing anything else, no timeout.
**Why bad:** If Kobalt is serving the other agent, this agent stalls indefinitely.
**Instead:** Set a reasonable timeout (30-60s) on each Kobalt call. If timeout exceeded, agent can re-use prior reasoning or submit a safe no-op.

---

## Scalability Considerations

This is a capstone project, not a production system. Scalability below the threshold of "works for a 20-minute demo" is out of scope.

| Concern | At Demo Scale (1 game) | If Extended |
|---------|----------------------|-------------|
| LLM contention | Acceptable queue delay | Separate GPU per agent |
| Battleground state reads | SSH polling is fine | Event-driven state push |
| Scoring granularity | 30-60s snapshot | Continuous event stream |
| Replayability | Docker Compose reset | Git-tagged snapshots |

---

## Sources

- [CybORG++: An Enhanced Gym for the Development of Autonomous Cyber Agents](https://arxiv.org/html/2410.16324v1) — architecture patterns for agent/environment separation
- [HackSynth: LLM Agent and Evaluation Framework for Autonomous Penetration Testing](https://arxiv.org/html/2412.01778v1) — Planner + Summarizer pattern for hacking agents
- [Security Patterns for Autonomous Agents: Lessons from Pentagi](https://www.sitepoint.com/security-patterns-for-autonomous-agents-lessons-from-pentagi/) — modular orchestrator + sandboxed executor architecture
- [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html) — execution isolation, memory poisoning defense
- [ISOLATEGPT: An Execution Isolation Architecture for LLM-Based Agentic Systems](https://cybersecurity.seas.wustl.edu/paper/wu2025isolate.pdf) — hub-and-spoke isolation pattern
- [KoboldCPP GitHub Wiki](https://github.com/LostRuins/koboldcpp/wiki) — Kobalt exposes OpenAI-compatible `/v1/chat/completions`
- [Docker Packet Filtering and Firewalls](https://docs.docker.com/engine/network/packet-filtering-firewalls/) — iptables isolation for container networks
- [Autonomous Red vs Blue Teaming: ISACA 2026](https://www.isaca.org/resources/news-and-trends/industry-news/2026/autonomous-red-vs-blue-teaming-a-new-frontier-in-cybersecurity-risk-and-reward) — circuit breaker patterns, sandbox digital twin concept
- [Agentic AI Architecture: Unstructured](https://unstructured.io/blog/defining-the-autonomous-enterprise-reasoning-memory-and-the-core-capabilities-of-agentic-ai) — Planner, Executor, Memory sub-component model
