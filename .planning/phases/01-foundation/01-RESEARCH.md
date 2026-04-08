# Phase 1: Foundation - Research

**Researched:** 2026-04-08
**Domain:** KoboldCpp inference, Docker networking isolation, LangGraph agent loop, FastAPI orchestrator, SQLite decision logging
**Confidence:** MEDIUM (most findings verified with official sources; CUDA 3.7 fallback path has one LOW-confidence item)

---

## Summary

This phase builds the complete infrastructure for the CyberSec AI Capstone: a K80 GPU running Gemma 4 via KoboldCpp, two isolated agent containers (red/blue) that SSH through a FastAPI orchestrator to a realistic battleground Ubuntu container, with LangGraph driving each agent's observe-reason-act loop and SQLite capturing decision traces.

The most critical validated finding is that **KoboldCpp does support K80 (CUDA 3.7), but requires the CUDA 11.4 build — not the default CUDA 12 binary**. This was a known regression that was fixed in a recent release. Gemma 4 E4B at Q4_K_M weighs ~5 GB and will fit comfortably in 24 GB VRAM with substantial headroom for KV cache and dual-model sequential loading.

Gemma 4 support was added to KoboldCpp in v1.111 (April 4, 2026) with a hotfix in v1.111.2 for format sensitivity. The model requires `--jinja` flag for correct chat template application, and tool/function calling format uses Gemma 4's native `<|tool_call>` special tokens, which KoboldCpp handles via its universal toolcalling module. If tool calls prove unreliable in practice, a structured JSON fallback (grammar sampling via GBNF) is available as a well-supported escape hatch.

Docker network isolation uses the proven pattern of two separate bridge networks with the orchestrator container attached to both — agents see only their own network and the orchestrator, never each other or the battleground directly.

**Primary recommendation:** Use KoboldCpp v1.111.2+ with the CUDA 11 binary, `--jinja` flag, single-instance serving one model at a time with admin-panel hot-swap for sequential red/blue turns.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| KoboldCpp | v1.111.2+ | Local LLM inference server | Only inference server confirmed to support K80 CUDA 3.7 + Gemma 4 GGUF |
| Gemma 4 E4B Q4_K_M | GGUF via Unsloth | LLM model | 5 GB fits 24 GB VRAM, dense architecture, native tool calling |
| LangGraph | 0.2.x (latest) | Agent state machine / loop | Purpose-built for stateful observe-reason-act cycles; native MemorySaver |
| FastAPI | 0.115.x | Orchestrator API server | Async-native, middleware support, easy Pydantic request validation |
| Paramiko | 3.x | SSH execution from orchestrator to battleground | Standard Python SSH client, exec_command() well-documented |
| Docker Compose | v2.x | Container orchestration | Multi-network support, named networks, service-level network assignment |
| SQLite | stdlib (Python) | Decision and game logging | Zero infrastructure overhead, suitable for single-node capstone scope |
| Rich | 13.x | Terminal display panels | Live panels, tables, syntax highlighting — no additional infra |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| langchain-openai | 0.2.x | LangChain OpenAI-compatible client | Connects LangGraph to KoboldCpp `/v1` endpoint |
| pydantic | 2.x | Request/response validation in FastAPI | Input validation for command submissions |
| python-dotenv | 1.x | Environment variable management | SSH credentials, port configs |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| KoboldCpp CUDA 11 build | Build from source with `-DGGML_CUDA_FORCE_CUBLAS=ON` + `CUDA_ARCH_LIST=3.7` | Build path is viable fallback if prebuilt fails; adds 30-60 min setup time |
| Gemma 4 E4B | Gemma 4 E2B (2B dense, ~2.5 GB Q4) | Drop if 5 GB + KV cache exceeds headroom; same Gemma 4 family per decision |
| LangGraph | Raw FSM with asyncio | LangGraph adds MemorySaver, RemoveMessage, checkpointing out-of-box; worth the dependency |
| Paramiko SSH | Docker exec API | SSH maintains the illusion that agents see a real remote server, not a container |

**Installation:**
```bash
pip install langgraph langchain-openai fastapi uvicorn paramiko pydantic python-dotenv rich
```

---

## Architecture Patterns

### Recommended Project Structure
```
project/
├── docker-compose.yml        # All services + network definitions
├── orchestrator/
│   ├── Dockerfile
│   ├── main.py               # FastAPI app entry
│   ├── safety_filter.py      # Blocklist middleware
│   ├── ssh_executor.py       # Paramiko SSH to battleground
│   └── db.py                 # SQLite schema + writes
├── agents/
│   ├── red_agent/
│   │   ├── Dockerfile
│   │   └── agent.py          # LangGraph loop for red agent
│   └── blue_agent/
│       ├── Dockerfile
│       └── agent.py          # LangGraph loop for blue agent
├── battleground/
│   ├── Dockerfile            # Ubuntu + web app + db + users
│   └── setup.sh              # Cron jobs, log seeding, service start
└── inference/
    └── start_koboldcpp.sh    # KoboldCpp launch with CUDA 11 flags
```

### Pattern 1: Dual Isolated Networks (Hub-and-Spoke)
**What:** Three bridge networks — `red-net`, `blue-net`, `orchestrator-net`. Red agent attaches to `red-net` + `orchestrator-net`. Blue agent attaches to `blue-net` + `orchestrator-net`. Battleground attaches to `orchestrator-net` only. Agents cannot reach each other or the battleground directly.
**When to use:** Always — this is the INFRA-01 isolation requirement.

```yaml
# docker-compose.yml excerpt
networks:
  red-net:
    driver: bridge
    internal: true
  blue-net:
    driver: bridge
    internal: true
  orchestrator-net:
    driver: bridge

services:
  orchestrator:
    networks:
      - red-net
      - blue-net
      - orchestrator-net

  red-agent:
    networks:
      - red-net          # can reach orchestrator, nothing else

  blue-agent:
    networks:
      - blue-net         # can reach orchestrator, nothing else

  battleground:
    networks:
      - orchestrator-net # only orchestrator can SSH here
```

### Pattern 2: LangGraph Observe-Reason-Act Loop
**What:** StateGraph with three nodes — `observe`, `reason`, `act` — plus a conditional edge that either continues the loop or exits after hitting turn limit. MemorySaver provides short-term memory. Long-term memory stored as JSON in SQLite.
**When to use:** Each agent has one graph instance running its turn loop.

```python
# Source: LangGraph docs + community guides (2025)
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import trim_messages

class AgentState(TypedDict):
    messages: list           # rolling message history
    turn: int
    findings: dict           # long-term JSON memory
    last_command: str
    last_output: str

def should_continue(state: AgentState) -> str:
    if state["turn"] >= MAX_TURNS:
        return END
    return "observe"

builder = StateGraph(AgentState)
builder.add_node("observe", observe_node)
builder.add_node("reason", reason_node)
builder.add_node("act", act_node)
builder.set_entry_point("observe")
builder.add_edge("observe", "reason")
builder.add_edge("reason", "act")
builder.add_conditional_edges("act", should_continue)

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)
```

### Pattern 3: Rolling Context Window with trim_messages
**What:** Keep last N messages by token count to stay within KoboldCpp's context limit without losing recent observations.

```python
# Source: LangChain memory docs
from langchain_core.messages import trim_messages

trimmed = trim_messages(
    state["messages"],
    max_tokens=4096,          # conservative for K80 KV cache budget
    strategy="last",          # keep most recent
    token_counter=llm,        # uses model tokenizer
    include_system=True,      # always keep system prompt
)
```

### Pattern 4: FastAPI Safety Filter as Middleware
**What:** Pydantic model validates command input; blocklist check happens before SSH dispatch. Blocked commands return 403 with reason logged to SQLite.

```python
# FastAPI orchestrator pattern
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

BLOCKLIST = [
    r"rm\s+-rf\s+/",
    r"reboot",
    r"shutdown",
    r"docker\s+",        # prevent container escape
    r"nsenter",
    r"chroot\s+/proc",
    r"mkfs\.",
    r"dd\s+if=.*of=/dev/",
]

class CommandRequest(BaseModel):
    agent: str           # "red" | "blue"
    command: str
    turn: int

@app.post("/execute")
async def execute(req: CommandRequest):
    for pattern in BLOCKLIST:
        if re.search(pattern, req.command, re.IGNORECASE):
            log_safety_activation(req, pattern)
            raise HTTPException(403, detail=f"Blocked: matched pattern '{pattern}'")
    output = await ssh_execute(req.command)
    log_decision(req, output)
    return {"output": output}
```

### Pattern 5: KoboldCpp Sequential Model Serving
**What:** Run one KoboldCpp instance. Red agent calls `/v1/chat/completions`, waits for response (blocking per turn). Blue agent then calls next turn. Sequential by design — no VRAM contention.
**When to use:** Single GPU, single model instance. No need to swap models since both agents use identical Gemma 4 E4B.

```bash
# start_koboldcpp.sh
./koboldcpp_cu11 \
  --model gemma-4-E4B-it-Q4_K_M.gguf \
  --usecuda \
  --gpulayers 99 \
  --contextsize 8192 \
  --port 5001 \
  --jinja \
  --host 0.0.0.0
```

### Anti-Patterns to Avoid
- **Two KoboldCpp processes on same GPU:** Will OOM. One process, sequential requests only.
- **Using CUDA 12 prebuilt with K80:** Will fail with "no kernel image available." Must use `koboldcpp_cu11` binary or build with CUDA arch 3.7.
- **Skipping `--jinja` flag:** Gemma 4 is format-sensitive. Without `--jinja`, outputs degrade or become malformed.
- **Agents connecting directly to battleground:** Defeats isolation requirement. All traffic must route through orchestrator `/execute`.
- **Storing tool definitions in message history:** Gemma 4 tool schema goes in system prompt only, not repeated per turn.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Agent state checkpointing | Custom dict persistence | LangGraph `MemorySaver` | Handles thread_id scoping, state replay, graph resumption |
| Message trimming | Manual list slicing | `trim_messages()` from langchain_core | Handles token counting, system prompt preservation |
| SSH connection pooling | Manual socket management | Paramiko `SSHClient` with `AutoAddPolicy` | Handles key negotiation, channel management, stdout/stderr separation |
| JSON schema output enforcement | Prompt engineering only | KoboldCpp grammar sampling (GBNF) or `response_format: {type: "json_object"}` | Prevents malformed JSON silently; grammar sampling is deterministic |
| Docker network isolation | iptables rules | Compose `internal: true` networks | Compose manages iptables rules; manual iptables conflicts with Docker's chain management |

**Key insight:** On a 2-day deadline, the correct answer to almost every infrastructure problem is "use what Compose/LangGraph/KoboldCpp already provides" rather than building custom control planes.

---

## Common Pitfalls

### Pitfall 1: K80 CUDA Kernel Mismatch
**What goes wrong:** Running the default KoboldCpp binary (CUDA 12) on K80 produces `CUDA error: no kernel image is available for execution on the device`. The GPU is detected but inference fails at the first forward pass.
**Why it happens:** KoboldCpp prebuilt CUDA 12 binaries are compiled for compute capability 5.0+. K80 is 3.7.
**How to avoid:** Always use the `koboldcpp_cu11` binary (CUDA 11.4 build). This binary explicitly supports compute 3.7 — K80 support was reinstated as of a recent release per GitHub issue #1409.
**Warning signs:** GPU is listed in `nvidia-smi` but KoboldCpp errors on startup or first generation request.

### Pitfall 2: Gemma 4 Format Sensitivity Without --jinja
**What goes wrong:** Chat completions return repetitive or truncated output; the model doesn't follow turn structure.
**Why it happens:** Gemma 4 has a non-standard jinja2 chat template baked into the GGUF. Without `--jinja`, KoboldCpp uses its generic adapter which doesn't match Gemma 4's expected token layout.
**How to avoid:** Always launch KoboldCpp with `--jinja` flag. Use `--jinja_tools` only if using the full function-calling pipeline.
**Warning signs:** Model responds with raw continuation instead of structured assistant turn.

### Pitfall 3: VRAM Exhaustion from Large Context
**What goes wrong:** Initial turns work; later turns OOM as KV cache grows. K80 has 24 GB but KV cache scales with `n_ctx * n_layers * 2 * head_size`.
**Why it happens:** Gemma 4 E4B has 42 layers. At 8192 context, KV cache is ~2-4 GB additional on top of the 5 GB model weights.
**How to avoid:** Start with `--contextsize 4096`. Monitor VRAM with `nvidia-smi` during first demo run. Increase only if reasoning quality demands it.
**Warning signs:** Segfault or CUDA OOM mid-generation rather than at startup.

### Pitfall 4: Docker Internal Network Blocks SSH Outbound
**What goes wrong:** Orchestrator container cannot SSH to battleground even though both are on `orchestrator-net`.
**Why it happens:** Using `internal: true` on the orchestrator-net prevents all external routing including intra-network. Only agent-facing networks (`red-net`, `blue-net`) should be `internal: true`.
**How to avoid:** Only mark `red-net` and `blue-net` as `internal: true`. `orchestrator-net` should be a normal bridge network (orchestrator needs to reach battleground and KoboldCpp, which may be on the host).
**Warning signs:** SSH connection timeouts from orchestrator to battleground with no error from the battleground container's sshd.

### Pitfall 5: Gemma 4 GGUF BOS Token Omission
**What goes wrong:** Model produces incoherent output from the first token.
**Why it happens:** Some early Gemma 4 GGUF files circulating on HuggingFace were uploaded without the BOS (beginning-of-sequence) token in the tokenizer config. This is a model file problem, not a KoboldCpp problem.
**How to avoid:** Use Unsloth's official GGUF repo (`unsloth/gemma-4-E4B-it-GGUF`). This was the source validated in KoboldCpp issue #2084 and confirmed working.
**Warning signs:** Immediate garbage output even with correct `--jinja` flag.

### Pitfall 6: Agent Commands Bypassing Orchestrator
**What goes wrong:** Agent directly imports Paramiko and SSH's to battleground, bypassing the safety filter.
**Why it happens:** If the agent's LangGraph tool definition includes a direct SSH tool rather than an HTTP call to the orchestrator.
**How to avoid:** Agent tools ONLY call `POST orchestrator:8080/execute`. No SSH library in agent containers. The battleground's port 22 is not mapped to any agent network.

---

## Code Examples

### KoboldCpp CUDA 11 Launch (K80 Safe)
```bash
# Source: KoboldCpp GitHub issue #1409, confirmed K80 support
./koboldcpp_cu11 \
  --model ./models/gemma-4-E4B-it-Q4_K_M.gguf \
  --usecuda \
  --gpulayers 99 \
  --contextsize 4096 \
  --port 5001 \
  --host 0.0.0.0 \
  --jinja \
  --threads 4
```

### LangGraph Agent with OpenAI-Compatible KoboldCpp
```python
# Source: LangGraph docs + langchain-openai docs
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://koboldcpp:5001/v1",
    api_key="dummy",            # KoboldCpp does not require real key
    model="koboldcpp",          # model name is ignored by KoboldCpp
    temperature=0.7,
    max_tokens=512,
)
```

### Paramiko SSH Execution (Orchestrator to Battleground)
```python
# Source: Paramiko official docs
import paramiko

def ssh_execute(command: str, timeout: int = 30) -> dict:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname="battleground",   # Docker service name resolves via DNS
        port=22,
        username="ctf_user",
        password="ctf_pass",
        timeout=10,
    )
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    client.close()
    return {"stdout": out, "stderr": err, "exit_code": exit_code}
```

### SQLite Schema for Decision and Game Logs
```python
# Design: dual-table — verbose reasoning log + structured game log
SCHEMA = """
CREATE TABLE IF NOT EXISTS decision_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL NOT NULL,           -- time.time()
    agent       TEXT NOT NULL,           -- 'red' | 'blue'
    turn        INTEGER NOT NULL,
    reasoning   TEXT,                    -- full LLM reasoning trace (verbose)
    intent      TEXT,                    -- one-line summary of what agent wants to do
    command     TEXT NOT NULL,
    stdout      TEXT,
    stderr      TEXT,
    exit_code   INTEGER,
    outcome     TEXT                     -- 'success' | 'fail' | 'blocked'
);

CREATE TABLE IF NOT EXISTS safety_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL NOT NULL,
    agent       TEXT NOT NULL,
    turn        INTEGER NOT NULL,
    command     TEXT NOT NULL,
    matched_pattern TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS findings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent       TEXT NOT NULL,
    ts          REAL NOT NULL,
    findings_json TEXT NOT NULL          -- JSON blob of key discoveries
);
"""
```

### Battleground Dockerfile Skeleton
```dockerfile
# Source: pattern, battleground container design
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    openssh-server \
    apache2 \
    mysql-server \
    cron \
    auditd \
    nmap \
    net-tools \
    curl wget vim \
    python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Create realistic users
RUN useradd -m -s /bin/bash alice && echo "alice:password123" | chpasswd
RUN useradd -m -s /bin/bash bob && echo "bob:letmein" | chpasswd
RUN useradd -m -s /bin/bash ctf_user && echo "ctf_user:ctf_pass" | chpasswd

# Seed realistic files, cron jobs, log entries
COPY setup.sh /setup.sh
RUN chmod +x /setup.sh && /setup.sh

EXPOSE 22 80 3306

CMD ["/usr/sbin/sshd", "-D"]
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| KoboldCpp CUDA 12 only | CUDA 11.4 build reinstated for K80 | Recent release (issue #1409 resolved) | K80 now first-class supported |
| Gemma 4 unsupported in KoboldCpp | Full support in v1.111 (April 4 2026) | April 4 2026 | Use v1.111.2+ minimum |
| Manual message list management | LangGraph `RemoveMessage` + `trim_messages` | LangGraph 0.2+ | Rolling context is built-in, not custom |
| Tool calls via raw prompt hacking | Gemma 4 native `<|tool_call>` tokens + `--jinja` | Gemma 4 architecture | Structured function calling without prompt engineering |

**Deprecated/outdated:**
- KoboldCpp `--useclblast`: Not applicable for NVIDIA. Use `--usecuda` with CUDA 11 binary.
- LangChain `ConversationBufferMemory`: Replaced by LangGraph MemorySaver for stateful graph agents.

---

## Open Questions

1. **Gemma 4 tool call reliability via KoboldCpp `--jinja`**
   - What we know: `--jinja` applies the correct GGUF template; Gemma 4 has native tool-call tokens
   - What's unclear: Whether KoboldCpp's universal toolcalling module correctly marshals `<|tool_call>` output into OpenAI `tool_calls` response format that LangChain parses
   - Recommendation: In Phase 1, implement a structured JSON fallback — prompt the model to return `{"command": "...", "reasoning": "..."}` with grammar sampling as backup. Test `--jinja_tools` mode in a smoke test before committing to it.

2. **KoboldCpp network reachability from orchestrator container**
   - What we know: KoboldCpp runs on the host (or a separate container) at port 5001
   - What's unclear: Whether host-mode networking or a dedicated `inference-net` is cleaner for the Compose setup
   - Recommendation: Run KoboldCpp on the host, expose via `host.docker.internal:5001` from orchestrator container. Simpler than adding a fifth container.

3. **K80 inference speed (tokens/sec)**
   - What we know: K80 CUDA 3.7, 10-15 TFLOPS FP32; Gemma 4 E4B Q4_K_M is ~5 GB
   - What's unclear: Expected tokens/sec on K80 for this model (K80 is old hardware)
   - Recommendation: Build in a 60-second inference timeout. If speed is unacceptable, drop to E2B (~2.5 GB) per the fallback decision.

---

## Sources

### Primary (HIGH confidence)
- KoboldCpp GitHub issue #1409 — K80 CUDA 3.7 compatibility and `koboldcpp_cu11` binary resolution
- KoboldCpp GitHub issue #2084 — Gemma 4 support added in v1.111, confirmed working with rolling release
- `unsloth/gemma-4-E4B-it-GGUF` HuggingFace page — Q4_K_M file size (4.98 GB), architecture (dense 42 layers, 4.5B params)
- Docker Compose official networking docs — multi-network service assignment, `internal: true` flag
- LangChain memory docs — `MemorySaver`, `trim_messages`, `RemoveMessage` APIs
- Paramiko official docs — `SSHClient.exec_command()` pattern

### Secondary (MEDIUM confidence)
- KoboldCpp wiki + API docs (`lite.koboldai.net/koboldcpp_api`) — OpenAI-compatible `/v1` endpoint, `--jinja` flag behavior, grammar sampling
- Gemma 4 WebSearch results — function calling token format, E4B VRAM range (6-8 GB for Q4_K_M)
- Docker Compose forum post on multiple networks and hub topology
- LangGraph community guides on short-term/long-term memory patterns (Oct 2025)

### Tertiary (LOW confidence)
- K80 inference speed estimates — based on hardware specs only, no empirical benchmark found for Gemma 4 E4B Q4_K_M on K80

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified with official sources or GitHub issues
- Architecture: HIGH — Docker networking and LangGraph patterns verified with official docs
- KoboldCpp K80 path: HIGH — specific GitHub issue with confirmed resolution found
- Gemma 4 tool calls via KoboldCpp: MEDIUM — support confirmed but integration behavior not empirically tested
- K80 inference speed: LOW — hardware spec extrapolation only

**Research date:** 2026-04-08
**Valid until:** 2026-04-22 (fast-moving: KoboldCpp releases frequently, recheck before build)
