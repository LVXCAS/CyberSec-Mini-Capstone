# Phase 2: Agents and Game - Research

**Researched:** 2026-04-08
**Domain:** Cybersecurity agent skill system, LangGraph tool dispatch, game loop orchestration
**Confidence:** MEDIUM (LangGraph verified via official docs; Gemma 4 tool format from community sources; cybersecurity tool patterns from existing frameworks)

---

## Summary

Phase 2 builds on the Phase 1 foundation (LangGraph + KoboldCpp + FastAPI + Paramiko + Docker + SQLite + Rich) to implement real cybersecurity skill execution by both agents, then wire those skills into a complete timed game with scoring. The three main concerns are: (1) how agents dispatch tools given Gemma 4's prompt-engineering-only tool calling, (2) how real Linux tools (nmap, hydra, UFW, etc.) get wrapped safely in Python, and (3) how the game loop coordinates two autonomous agents simultaneously without deadlock or race conditions.

The standard approach is a custom LangGraph dispatch node that parses the LLM's text output for a tool name and arguments using regex/JSON extraction, executes the matching Python function (which shells out via subprocess), then returns results to the agent state. This bypasses LangGraph's native ToolNode (which requires the LLM to emit structured `tool_calls` objects — Gemma 4 cannot reliably do this). Game state is managed by a single-writer SQLite thread using WAL mode, with snapshots on a timer.

**Primary recommendation:** Build a custom LangGraph node called `tool_dispatcher` that parses agent output and calls skill functions. Do NOT use LangGraph's built-in ToolNode. Use subprocess with enforced timeouts for all tool execution. A queue-based SQLite writer handles all game state writes.

---

## Standard Stack

### Core (locked from Phase 1)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| langgraph | >=0.2 (stable 1.0) | Agent state machine and loops | Already chosen; hub-and-spoke pattern |
| paramiko | >=3.x | SSH execution into battleground | Already chosen |
| python-nmap | 0.7.1 | Nmap output parsing | Wraps XML output into dict; avoids manual parsing |
| subprocess (stdlib) | Python 3.11+ | Shell tool execution with timeout | No dependency; supports timeout param |
| sqlite3 (stdlib) | Python 3.11+ | Game log and state | Already chosen; WAL mode for concurrent reads |
| threading.Queue (stdlib) | Python 3.11+ | Serialize SQLite writes | Standard pattern for single-writer SQLite |
| asyncio (stdlib) | Python 3.11+ | Action queue between agents | Coordinates simultaneous submit, sequential execute |
| rich | >=13.x | Real-time agent reasoning display | Already chosen |
| fastapi | >=0.110 | Orchestrator HTTP layer | Already chosen |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-nmap | 0.7.1 | Parse nmap XML output into dict | All RED-01 recon skills |
| schedule | >=1.2 | Periodic snapshot timer | GAME-03 every 30-60 sec |
| dataclasses / pydantic | stdlib / >=2.x | Skill result schema | Validate tool output before state update |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| python-nmap | subprocess + XML parse | python-nmap handles edge cases; use it |
| schedule | asyncio.sleep loop | schedule is simpler for periodic tasks; either works |
| threading.Queue writer | SQLAlchemy async | Overkill for SQLite; queue pattern is 10 lines |

### Installation
```bash
pip install python-nmap schedule pydantic
# nmap, hydra, iptables/ufw installed in container Dockerfiles
```

---

## Architecture Patterns

### Recommended Project Structure
```
src/
├── skills/
│   ├── red/              # RED-01 through RED-04 implementations
│   │   ├── recon.py      # nmap, service enum
│   │   ├── exploit.py    # hydra brute force, service exploits
│   │   ├── privesc.py    # SUID, sudo misconfig
│   │   └── persistence.py # backdoor user, cron, SSH keys
│   ├── blue/             # BLUE-01 through BLUE-04
│   │   ├── harden.py     # UFW rules, service config, user lockdown
│   │   ├── detect.py     # log tail, netstat, ps monitoring
│   │   ├── respond.py    # kill PID, remove user, block IP
│   │   └── uptime.py     # service health check, restart
│   └── registry.py       # SKILL_REGISTRY dict: name -> callable
├── agents/
│   ├── graph.py          # LangGraph StateGraph definition
│   ├── nodes.py          # reason_node, tool_dispatcher node
│   └── prompts.py        # system prompts with persona
├── game/
│   ├── loop.py           # main game loop, phase timer, action queue
│   ├── scoring.py        # score calculation, win condition checks
│   ├── snapshots.py      # periodic state snapshot to SQLite
│   └── narrative.py      # final story-format summary generator
├── db/
│   ├── writer.py         # single-thread SQLite writer with Queue
│   └── schema.sql        # tables: game_events, snapshots, scores
└── display/
    └── terminal.py       # Rich live display, reasoning stream
```

### Pattern 1: Custom Tool Dispatcher Node (Critical)

**What:** A LangGraph node that parses agent text output for a tool call, looks it up in a registry, executes it, and appends the result to agent state. Replaces the built-in ToolNode.

**Why:** Gemma 4 uses prompt-engineering-only function calling — it emits text like `{"name": "port_scan", "parameters": {"target": "10.0.0.5"}}`, not the structured `tool_calls` AIMessage field that ToolNode requires.

**How it works:**
```python
# Source: LangGraph docs + Gemma 4 tool calling pattern (Simon Willison, Mar 2025)
import re, json

SKILL_REGISTRY = {}  # populated in skills/registry.py

def tool_dispatcher(state: AgentState) -> AgentState:
    last_message = state["messages"][-1].content

    # Try JSON extraction first
    match = re.search(r'\{[^{}]*"name"[^{}]*\}', last_message, re.DOTALL)
    if not match:
        # Fallback: try Python-style [func_name(key=val)]
        match = re.search(r'\[(\w+)\((.+?)\)\]', last_message)
        if not match:
            return state  # no tool call found, route back to reason

    try:
        call = json.loads(match.group(0))
        skill_name = call["name"]
        params = call.get("parameters", {})
    except (json.JSONDecodeError, KeyError):
        return {**state, "tool_error": "parse_failed"}

    if skill_name not in SKILL_REGISTRY:
        return {**state, "tool_error": f"unknown_skill:{skill_name}"}

    result = SKILL_REGISTRY[skill_name](**params)  # execute skill
    return {
        **state,
        "last_tool_result": result,
        "messages": state["messages"] + [ToolMessage(content=str(result), tool_call_id="manual")]
    }
```

**Routing:** After `tool_dispatcher`, a conditional edge checks if a result exists → loop back to `reason_node`. If no tool call found in reason output → end or loop.

### Pattern 2: Skill Functions with Subprocess + Timeout

**What:** Each skill is a plain Python function that shells out to real tools, captures output, returns a structured dict.

**Critical:** All subprocess calls MUST have a timeout. Nmap `-T4` scans can take 2+ minutes without one.

```python
# Source: python-nmap PyPI docs + subprocess best practices
import subprocess, nmap

def port_scan(target: str, ports: str = "1-1000") -> dict:
    """RED-01: Reconnaissance - port scan target"""
    nm = nmap.PortScanner()
    nm.scan(target, ports, arguments="-T4 -sV --open")

    open_ports = []
    for host in nm.all_hosts():
        for proto in nm[host].all_protocols():
            for port in nm[host][proto].keys():
                if nm[host][proto][port]["state"] == "open":
                    open_ports.append({
                        "port": port,
                        "service": nm[host][proto][port].get("name", ""),
                        "version": nm[host][proto][port].get("version", "")
                    })
    return {"target": target, "open_ports": open_ports}

def ssh_brute(target: str, username: str, wordlist: str = "/usr/share/wordlists/rockyou.txt") -> dict:
    """RED-02: Exploitation - SSH credential attack"""
    try:
        result = subprocess.run(
            ["hydra", "-l", username, "-P", wordlist, f"ssh://{target}", "-t", "4", "-f"],
            capture_output=True, text=True, timeout=120
        )
        found = "login:" in result.stdout
        cred = None
        if found:
            import re
            m = re.search(r'login: (\S+) password: (\S+)', result.stdout)
            cred = {"user": m.group(1), "password": m.group(2)} if m else None
        return {"success": found, "credential": cred}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "timeout"}
```

### Pattern 3: Blue Skills via Paramiko (SSH into battleground)

**What:** Blue agent executes hardening/response commands on the battleground container via SSH (Paramiko), not via subprocess directly, because the blue agent container is separate from the battleground.

```python
# Source: Paramiko docs
import paramiko

def block_ip(ssh_client: paramiko.SSHClient, ip: str) -> dict:
    """BLUE-03: Response - block IP via UFW"""
    _, stdout, stderr = ssh_client.exec_command(
        f"sudo ufw deny from {ip} to any", timeout=15
    )
    stdout.channel.recv_exit_status()  # wait for completion
    return {"blocked": ip, "success": stderr.read().decode() == ""}

def kill_process(ssh_client: paramiko.SSHClient, pid: int) -> dict:
    """BLUE-03: Response - kill unauthorized process"""
    _, stdout, stderr = ssh_client.exec_command(f"kill -9 {pid}", timeout=10)
    exit_code = stdout.channel.recv_exit_status()
    return {"killed": pid, "success": exit_code == 0}
```

### Pattern 4: Game Loop with Action Queue

**What:** Both agents submit actions to a shared asyncio.Queue. The orchestrator processes one at a time (required by sequential KoboldCpp inference). Phase timer runs alongside.

```python
# Conceptual structure
import asyncio, time

async def game_loop():
    action_queue = asyncio.Queue()
    game_start = time.time()

    # Blue setup phase: only blue runs for 5 minutes
    await run_setup_phase(blue_agent, action_queue, duration=300)

    # Battle phase: both agents submit, orchestrator processes sequentially
    battle_task = asyncio.gather(
        agent_loop(red_agent, action_queue),
        agent_loop(blue_agent, action_queue),
        process_action_queue(action_queue, game_start)
    )

    try:
        await asyncio.wait_for(battle_task, timeout=1200)  # 20 min
    except asyncio.TimeoutError:
        pass  # time expiry win condition

    return generate_game_result()
```

### Pattern 5: SQLite Single-Writer Thread

**What:** One dedicated thread owns all SQLite writes. All other threads enqueue via threading.Queue.

```python
import sqlite3, threading, queue

class DBWriter:
    def __init__(self, db_path):
        self._q = queue.Queue()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        threading.Thread(target=self._worker, daemon=True).start()

    def write(self, sql, params=()):
        self._q.put((sql, params))

    def _worker(self):
        while True:
            sql, params = self._q.get()
            self._conn.execute(sql, params)
            self._conn.commit()
```

### Anti-Patterns to Avoid
- **Using LangGraph's built-in ToolNode:** Requires `tool_calls` field in AIMessage. Gemma 4 cannot reliably emit this format. Use custom dispatcher instead.
- **Running nmap without timeout:** A `-sV` scan on a range can block indefinitely. Always pass `timeout=` to subprocess.
- **Multiple threads writing to SQLite directly:** Will cause "database is locked" errors under concurrent agent load. Use the single-writer queue pattern.
- **Executing blue skills via subprocess inside blue-agent container:** Blue agent is separate from battleground. All battleground commands go through Paramiko SSH.
- **Running inference for both agents concurrently:** KoboldCpp is sequential. The action queue pattern serializes inference calls naturally.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Nmap output parsing | Custom XML parser | python-nmap | Handles all nmap output variants, host states, protocols |
| SSH key management | Custom key rotation logic | Paramiko + paramiko-expect | Paramiko handles key auth, channel management, timeouts |
| Periodic snapshots | Custom timer thread | `schedule` library or `asyncio.sleep` loop | 3 lines vs. 30; handles drift |
| Game time management | Custom datetime math | `time.monotonic()` + threshold checks | Monotonic avoids clock skew issues |
| Scoring persistence | Custom file format | SQLite with WAL | Already in stack; concurrent reads while writing |

**Key insight:** The skill implementations themselves look simple (one subprocess call) but the error handling, timeout management, output parsing, and result normalization are where the complexity lives. Each skill needs a consistent return schema so the agent can reason about results.

---

## Common Pitfalls

### Pitfall 1: Gemma 4 JSON Drift
**What goes wrong:** Gemma 4 will sometimes emit valid reasoning text without a tool call, emit malformed JSON, or include extra prose around the JSON object. The dispatcher fails to parse and either errors or loops infinitely.
**Why it happens:** Prompt-engineering tool calling is probabilistic. The Phase 1 research already noted regex fallback is needed.
**How to avoid:** Layer extraction attempts: (1) strict JSON parse of entire last message, (2) regex to extract first `{...}` block, (3) Python-style `[func(k=v)]` pattern, (4) if all fail, treat as a "think" turn and loop back to reason with a hint.
**Warning signs:** Agent reasoning loop exceeds 5 turns without a tool result.

### Pitfall 2: Nmap NET_ADMIN Capabilities in Docker
**What goes wrong:** Nmap SYN scans (`-sS`) require raw socket access. Docker containers don't have this by default. You get "Operation not permitted" or silently falls back to TCP connect scan.
**Why it happens:** Docker drops `NET_ADMIN` and `NET_RAW` capabilities by default.
**How to avoid:** Either (a) use TCP connect scan (`-sT`) which needs no special caps — fine for CTF, or (b) add `cap_add: [NET_ADMIN, NET_RAW]` to the red-agent container in docker-compose.yml. Option (a) is safer and sufficient.
**Warning signs:** Nmap returns no results on a host you know has open ports.

### Pitfall 3: Hydra Rate Limiting Itself
**What goes wrong:** Hydra `-t 4` (4 threads) plus SSH rate limiting in the battleground makes brute force take longer than the 20-minute game window. Red agent waits, burns turns.
**Why it happens:** sshd default MaxAuthTries is 6 per connection, causing per-connection restarts.
**How to avoid:** Configure the battleground sshd with high MaxAuthTries (e.g., 20) and weak passwords that are early in rockyou.txt (first 100 lines). The game is a demo, not a real pentest.
**Warning signs:** Hydra never returns within turn timeout.

### Pitfall 4: Blue Agent Detecting Its Own Actions
**What goes wrong:** Blue agent's log-monitoring skill picks up its own SSH connections (blue agent → battleground via Paramiko) and flags them as suspicious.
**Why it happens:** Fog of war — agents only see battleground state, not each other's source IPs. If blue doesn't know its own IP, it can misidentify itself.
**How to avoid:** Whitelist the blue-agent container IP in the detection skill. This IP is known at compose time via static container networking.
**Warning signs:** Blue agent keeps blocking and unblocking the same IP.

### Pitfall 5: SQLite Snapshot Blocking Action Processing
**What goes wrong:** Snapshot thread holds write lock at the same moment the action queue tries to log an event, causing a delay spike that disrupts game timing.
**Why it happens:** WAL mode allows concurrent reads but still serializes writes.
**How to avoid:** Snapshots go through the same DBWriter queue, not a separate connection. This makes snapshots wait their turn like any other write. Snapshot frequency 60s is fine for 20-minute game.
**Warning signs:** Action processing latency spikes every 30-60 seconds.

### Pitfall 6: Fog of War Implementation
**What goes wrong:** If battleground state query returns everything, agents trivially know what each other did. If it returns nothing, agents can't reason effectively.
**Why it happens:** Lazy state API design.
**How to avoid:** Define "battleground view" as what's observable from the agent's role: Red sees open ports, running services, and its own shell sessions. Blue sees system logs, active connections, running processes, and user accounts. Neither sees the other agent's LangGraph state, action log, or turn history. Implement two different `get_battleground_state()` functions — one per agent perspective.
**Warning signs:** Agent reasoning references the other agent's actions by name without having detected them.

---

## Code Examples

### Gemma 4 Tool Call Prompt Template
```python
# Source: Simon Willison (Mar 2025) + Gemma 4 format from KoboldCpp issue #2084
TOOL_CALL_SYSTEM = """You are a {role} agent in a cybersecurity exercise.

You have access to the following skills:
{skill_list_json}

When you want to use a skill, output ONLY a JSON object in this format:
{{"name": "skill_name", "parameters": {{"key": "value"}}}}

When you want to reason without acting, write your thoughts in plain text.
Do not mix JSON tool calls with reasoning text in the same response."""

# skill_list_json example:
# [{"name": "port_scan", "description": "Scan target for open ports", "parameters": {"target": "IP address", "ports": "port range like 1-1000"}}]
```

### Gemma 4 Chat Format for KoboldCpp
```python
# Source: KoboldCpp issue #2084, bartowski GGUF card
# Gemma 4 is format-sensitive. Use --jinja flag in KoboldCpp for automatic template.
# When calling API manually, build prompt like:
def build_prompt(system: str, messages: list[dict]) -> str:
    parts = [f"<|turn>system\n{system}<turn|>\n"]
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        parts.append(f"<|turn>{role}\n{msg['content']}<turn|>\n")
    parts.append("<|turn>model\n")
    return "<bos>" + "".join(parts)

# KoboldCpp generate call
import httpx
def generate(prompt: str, max_tokens: int = 512, stop: list[str] = None) -> str:
    resp = httpx.post("http://koboldcpp:5001/api/v1/generate", json={
        "prompt": prompt,
        "max_length": max_tokens,
        "max_context_length": 2048,
        "temperature": 0.7,
        "stop_sequence": stop or ["<turn|>", "<|turn>"],
        "trim_stop": True
    })
    return resp.json()["results"][0]["text"]
```

### LangGraph Agent StateGraph Skeleton
```python
# Source: LangGraph docs (langgraph.com) + custom dispatcher pattern
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    last_tool_result: dict | None
    tool_error: str | None
    turn_count: int
    game_context: dict  # battleground state snapshot

def route_after_reason(state: AgentState) -> str:
    """Route: did LLM output a tool call or just reasoning?"""
    last = state["messages"][-1].content
    if re.search(r'\{[^{}]*"name"[^{}]*\}', last):
        return "tool_dispatcher"
    if state["turn_count"] > 10:
        return END  # prevent infinite loops
    return "reason"  # keep thinking

graph = StateGraph(AgentState)
graph.add_node("reason", reason_node)
graph.add_node("tool_dispatcher", tool_dispatcher)
graph.set_entry_point("reason")
graph.add_conditional_edges("reason", route_after_reason)
graph.add_edge("tool_dispatcher", "reason")  # always reason after tool
agent = graph.compile()
```

### Scoring Schema
```python
# Two-layer scoring: competitive points + reasoning quality
# Point categories (Claude's discretion as per CONTEXT.md)
SCORING = {
    # Red competitive points
    "recon_complete": 5,
    "service_exploited": 15,
    "privesc_achieved": 20,
    "persistence_installed": 20,
    "full_kill_chain": 40,  # bonus for completing all 4

    # Blue competitive points
    "vuln_patched": 10,
    "attack_detected": 10,
    "attacker_blocked": 15,
    "service_kept_up": 5,   # per service, per check period
    "lockout_achieved": 40,  # red has no more attack paths

    # Stealth/detection bonuses (Claude's discretion)
    "red_undetected_action": 5,   # red action not detected by blue
    "blue_detected_stealthily": 5, # blue detected but didn't alert red

    # Reasoning quality (AI showcase layer)
    "pivot_on_failure": 3,      # agent explained why it failed and changed plan
    "correct_inference": 3,     # agent inferred other side's action correctly
    "adaptive_escalation": 5,   # red escalated strategy under time pressure
}
```

---

## Skill Design Recommendations (Claude's Discretion)

Per CONTEXT.md, skill granularity is at Claude's discretion. Recommendation: **multi-step recipe skills** rather than atomic commands.

**Rationale:** With 512 output tokens and ~2048 context, each agent turn is expensive (sequential KoboldCpp). Atomic skills (e.g., "run this exact nmap flag") waste turns on orchestration the LLM doesn't need to manage. Recipe skills bundle a logical objective so the LLM picks the goal, not the flags.

**Recommended skill granularity:**

| Skill ID | Name | What It Does | Input |
|----------|------|-------------|-------|
| `port_scan` | Port Scan | nmap -T4 -sV top 1000 ports | target IP |
| `service_enum` | Service Enum | nmap script scan on specific port | target, port |
| `ssh_brute` | SSH Brute Force | hydra SSH against target | target, username |
| `web_sqli_check` | SQLi Check | sqlmap basic check on URL | url |
| `find_suid` | Find SUID Bins | find / -perm -4000 via SSH | (none - uses battleground SSH) |
| `add_backdoor_user` | Add Backdoor User | useradd + set password | username, password |
| `install_cron_backdoor` | Cron Backdoor | crontab reverse shell entry | callback_ip, port |
| `add_ssh_key` | SSH Key Persistence | append to authorized_keys | target_user, pubkey |
| `block_ip` | Block IP | ufw deny from IP | ip |
| `kill_process` | Kill Process | kill -9 PID | pid |
| `remove_user` | Remove User | userdel -r username | username |
| `fix_suid` | Fix SUID | chmod -s on binary | binary_path |
| `harden_ssh` | Harden SSH | PermitRootLogin no, PasswordAuth no | (none) |
| `check_service` | Check Service | systemctl is-active | service_name |
| `restart_service` | Restart Service | systemctl restart | service_name |
| `scan_processes` | Scan Processes | ps aux + netstat -tlnp | (none) |
| `tail_auth_log` | Tail Auth Log | last 50 lines of /var/log/auth.log | (none) |
| `list_users` | List Users | /etc/passwd non-system users | (none) |

**Detection mechanism (Claude's discretion):** Active polling. Blue agent calls `scan_processes`, `tail_auth_log`, `list_users` on its turns. This is simpler to reason about for Gemma 4 than event-driven callbacks — the agent sees concrete data and reasons about what changed. Polling fits the turn-based game model.

**Stealth/detection bonus mechanic (Claude's discretion):** If red performs an action and blue does NOT detect it within 2 turns (blue doesn't call `tail_auth_log` or it calls it but the LLM doesn't flag it), red earns the stealth bonus. Tracked by comparing action timestamps in the event log against blue's detection event timestamps.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ToolNode for all LLMs | Custom dispatcher for local LLMs without native tool_calls | 2024 (local LLM rise) | Must implement manually; ToolNode unusable with Gemma 4 |
| Gemma 3 function calling | Gemma 4 adds `<|channel>thought` thinking tokens | Apr 2026 | Can use thinking output for reasoning display; disable with --chat-template-kwargs |
| KoboldCpp manual prompt assembly | KoboldCpp --jinja flag auto-applies Gemma 4 template | v1.111 (Apr 2026) | Use --jinja flag; don't manually build chat format |
| nmap subprocess only | python-nmap for Python-native parsing | Stable | python-nmap wraps nmap and handles XML reliably |

**Deprecated/outdated:**
- Manual Gemma 4 chat template construction: --jinja flag in KoboldCpp handles it automatically (v1.111+). Only needed if calling raw `/api/v1/generate` endpoint instead of `/v1/chat/completions`.
- LangGraph ToolNode with local LLMs lacking `tool_calls` support: custom dispatcher is the correct pattern.

---

## Open Questions

1. **Gemma 4 model size vs. available VRAM on K80**
   - What we know: K80 has 12GB VRAM, CUDA 3.7 (no Flash Attention). Gemma-4-E4B is a 4B MoE model. Gemma-4-27B-A4B is the larger variant.
   - What's unclear: Which quantization level (Q4_K_M, Q5_K_M) fits in K80's 12GB while leaving headroom for context. E4B should fit; 27B-A4B may not.
   - Recommendation: Phase 1 should have validated this. If E4B quality is insufficient for tool-call parsing, the custom dispatcher regex fallback must be robust.

2. **Hydra timeout vs. weak passwords**
   - What we know: Hydra SSH brute force takes variable time depending on sshd config and wordlist position.
   - What's unclear: Exact time to crack a password in the first 50 lines of rockyou.txt against a lightly configured sshd in a Docker container.
   - Recommendation: Configure battleground weak passwords to be in the first 20 lines of rockyou.txt. Test this before the game runs.

3. **KoboldCpp --jinja vs. raw /api/v1/generate**
   - What we know: --jinja flag auto-applies Gemma 4 chat template when using `/v1/chat/completions`. The raw `/api/v1/generate` needs manual prompt construction.
   - What's unclear: Which endpoint Phase 1 used. If it used raw generate, prompts must be manually constructed with Gemma 4 format.
   - Recommendation: Migrate to `/v1/chat/completions` with --jinja flag for cleaner prompt management. Verify this is compatible with the Phase 1 KoboldCpp integration.

---

## Sources

### Primary (HIGH confidence)
- KoboldCpp API docs (lite.koboldai.net/koboldcpp_api) — endpoint parameters, stop_sequence, max_length
- LangGraph official docs (langchain.com/langgraph) — ToolNode limitations, StateGraph pattern, conditional edges
- python-nmap PyPI (pypi.org/project/python-nmap) — scan API and output structure
- SQLite WAL docs (sqlite.org/wal.html) — concurrent read/write behavior

### Secondary (MEDIUM confidence)
- KoboldCpp GitHub issue #2084 — Gemma 4 support, prompt format `<|turn>...<turn|>`
- bartowski/google_gemma-4-E4B-it-GGUF HuggingFace card — token format confirmation
- BlueLinuxBastion GitHub (fulco/BlueLinuxBastion) — blue team hardening command patterns
- RedAmon GitHub (samugit83/redamon) — LangGraph cybersecurity agent architecture reference

### Tertiary (LOW confidence — verify before use)
- Simon Willison blog (Mar 2025) — Gemma 3 function calling prompt format (Gemma 4 may differ)
- SQLite Worker Medium article — single-writer queue pattern (matches official sqlite.org guidance)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all from locked Phase 1 decisions + python-nmap is well-documented
- LangGraph tool dispatcher pattern: MEDIUM — pattern is well understood; custom implementation detail is new
- Gemma 4 prompt format: MEDIUM — verified from KoboldCpp community and HuggingFace model card
- Cybersecurity skill implementations: MEDIUM — subprocess + python-nmap patterns are stable
- Game loop architecture: MEDIUM — asyncio.Queue pattern is standard; specific integration is new

**Research date:** 2026-04-08
**Valid until:** 2026-05-08 (30 days — KoboldCpp releases fast; check for Gemma 4 support updates)
