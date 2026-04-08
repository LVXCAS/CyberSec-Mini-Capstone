# Technology Stack

**Project:** Autonomous Cybersecurity AI Agents (Red vs Blue)
**Researched:** 2026-04-08
**Research Mode:** Ecosystem

---

## Recommended Stack

### Agent Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| LangGraph | 0.2.x+ | Agent state machine, tool routing, multi-agent coordination | Graph-first approach gives explicit, debuggable state transitions ideal for the plan→execute→observe loop that cybersecurity agents require. Stateful by default — critical for tracking attack/defense history across a match. Supports conditional edges (route tool output to next action), human-in-the-loop for replay/pause, and durable execution. CrewAI abstracts too much; for a simulation where transparency and determinism matter, LangGraph's explicit graph beats CrewAI's role-playing model. |
| LangChain Core | 0.3.x+ | Tool definitions, message formatting, LLM interface | LangGraph is built on LangChain Core. Provides the `@tool` decorator, `ToolMessage` types, and structured output parsers needed to define shell-command tools cleanly. |

**Do NOT use:** CrewAI — too opinionated about agent roles, hides state transitions, harder to replay deterministically. AutoGen — Microsoft-backed, async multi-agent model adds complexity without benefit for a 2-agent competition. Pure ReAct loop without a framework — insufficient state management for multi-phase game.

---

### LLM Inference (Local)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| KoboldCpp | Latest stable (1.76+) | Inference server for Gemma 4 GGUF on K80 GPU | Exposes OpenAI-compatible `/v1/chat/completions` endpoint. LangChain has a native `ChatOpenAI` integration that can point at any OpenAI-compatible base URL. KoboldCpp handles GGUF model format natively, runs on CUDA (K80 is CUDA-capable, compute capability 3.7), supports streaming responses. Single binary, low operational overhead. |
| Gemma 4 E4B (or E2B) GGUF | Q4_K_M quantization | The agent "brain" powering red and blue team reasoning | Gemma 4's Mixture-of-Experts variants (E2B activates 2B params, E4B activates 4B params from 26B total) run nearly as fast as a dense 4B model. On a 24GB K80, a Q4_K_M quantized E4B sits at ~5-8GB VRAM — comfortably fits twice (one inference server serving both agents sequentially, or two separate processes if VRAM allows). Gemma 4 has native tool-use/function-calling support, which LangGraph leverages directly. Apache 2.0 license — no legal friction. |

**CRITICAL WARNING — K80 Compatibility:** The K80 is CUDA compute capability 3.7. KoboldCpp with CUDA support compiles against older compute targets. Gemma 4 GGUF via llama.cpp backend (which KoboldCpp uses) does not require modern CUDA features — Q4 quantized inference on K80 is feasible but slow. Expect 2-10 tokens/second depending on quantization level. This is acceptable for a demo/simulation; it is NOT acceptable for real-time interactive pentesting. Plan for agent turns taking 30-120 seconds each.

**Quantization recommendation:** Q4_K_M for E4B. Do not attempt Q8 or F16 on a 24GB K80 — VRAM will be exceeded. If token generation is too slow, drop to E2B at Q4_K_M.

**Do NOT use:** Ollama — does not support K80 (CUDA 3.7 is below minimum for modern Ollama builds). vLLM — requires CUDA 8.0+. llama.cpp directly — KoboldCpp wraps it with better API surface; no reason to use raw llama.cpp.

---

### LLM Integration (Python side)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| langchain-openai | 0.1.x+ | Connect LangGraph agents to KoboldCpp inference server | `ChatOpenAI(base_url="http://kobold-host:5001/v1", api_key="ignored")` — KoboldCpp's OpenAI-compatible endpoint accepts this directly. Zero custom code needed for the LLM integration layer. |
| Pydantic v2 | 2.x | Structured tool outputs, scoring schemas, game state models | LangGraph and LangChain use Pydantic v2 internally. Use it for `GameState`, `AgentAction`, `ScoreCard` models. Immutable models (`model_config = ConfigDict(frozen=True)`) prevent silent mutation bugs. |

---

### Command Execution (Agent → Battleground VM)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Paramiko | 3.x | SSH-based shell execution from agent containers to battleground VM | Each agent VM needs to issue shell commands (`nmap`, `iptables`, exploit scripts) on the battleground VM. Paramiko provides programmatic SSH with interactive shell sessions, output capture, and timeout control. It's a pure-Python SSH2 implementation — no system-level SSH binary dependency inside containers. Supports key-based auth (no passwords in code). |
| Docker SDK for Python (`docker`) | 7.x | Agent VMs that need to inspect or restart containers (game orchestrator use) | The orchestrator/scorer needs to query container state, read logs, and manage the battleground VM lifecycle. The official Docker SDK wraps the Docker daemon socket cleanly. Agents themselves do NOT get access to the Docker socket — that is a sandbox escape vector. |
| Python `subprocess` | stdlib | Local command execution within agent's own container | For commands the agent needs to run locally (e.g., generating payloads, running local recon scripts). Use `subprocess.run(..., timeout=30, capture_output=True)` exclusively. Never `shell=True` — use argument lists to prevent injection. |

**Architecture decision:** Agents connect to battleground via SSH (Paramiko), NOT via shared Docker volumes or direct `docker exec`. This preserves the physical isolation of the network topology and makes command execution realistic (SSH is what real attackers use). The battleground VM runs an OpenSSH server; red agent is given credentials with limited privilege, blue agent with sudo.

**Do NOT use:** `docker exec` for agent commands — breaks the simulation realism and bypasses network-layer security controls. `fabric` — wraps Paramiko but adds unnecessary abstraction for this use case. `asyncssh` — async SSH is more complex; synchronous Paramiko is sufficient for turn-based agent execution.

---

### Docker Orchestration

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Docker Compose | v2 (Compose spec 5.x) | Define and manage the 3-VM architecture | The 3-container setup (red-agent, blue-agent, battleground) plus optional scorer container maps directly to a `compose.yml`. Compose v2 handles inter-container networking, named networks (isolating agent containers from each other), volume mounts for memory persistence, and environment variable injection. For a capstone demo, this is the right complexity level — no Kubernetes. |
| Docker Bridge Networks | — | Network isolation between agents | Define separate Docker bridge networks: `red-net` (red-agent ↔ battleground), `blue-net` (blue-agent ↔ battleground). Agents cannot reach each other's container directly. Battleground is on both networks. Scorer/orchestrator is on all three. |

**Compose structure:**
```
services:
  battleground:         # Ubuntu 22.04, OpenSSH, vulnerable services
  red-agent:            # Python app + LangGraph agent, on red-net only
  blue-agent:           # Python app + LangGraph agent, on blue-net only
  scorer:               # Game orchestrator, on all nets, Docker socket access
  kobold-inference:     # KoboldCpp server, GPU passthrough (--gpus)
```

**Do NOT use:** Kubernetes — massive operational overhead for a 5-container demo. Docker Swarm — adds clustering complexity with no benefit. Raw `docker run` commands — not reproducible for presentation.

---

### Scoring Engine

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python (FastAPI) | 0.115.x | Scoring API and game orchestration server | The scorer needs to: receive game events from both agents, evaluate rule conditions (flag captured, service restored, etc.), compute scores, and serve a live dashboard. FastAPI gives async HTTP endpoints, automatic OpenAPI docs (useful for demo), and Pydantic integration for event schemas. Agents POST events to the scorer; scorer maintains authoritative game state. |
| SQLite (via aiosqlite) | — | Persistent game log for replay | All agent actions, commands issued, LLM reasoning traces, and score changes are written to SQLite. This enables post-game replay and presentation-mode review. SQLite requires no server process — file-based, bundled with Python. |
| Rich (Python library) | 13.x | Terminal dashboard for live simulation display | Rich provides live-updating terminal tables and panels. A `rich.live.Live` panel showing red-agent actions, blue-agent actions, and current score side-by-side gives a compelling presentation output without needing a web frontend. |

**Do NOT use:** PostgreSQL — overkill for a bounded simulation. Redis — unnecessary pub/sub complexity. A web dashboard (React/Vue) — timeline risk; terminal Rich dashboard is faster to build and equally compelling for a capstone demo.

---

### Agent Memory

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| LangGraph `MemorySaver` | Built-in | Checkpointed in-run memory (conversation history, tool results) | LangGraph's built-in checkpoint system persists the full agent graph state between turns. This is the primary short-term memory mechanism — the agent "remembers" what commands it ran and what output it got without re-querying. |
| JSON files (stdlib) | — | Cross-run skill memory and target notes | Each agent maintains a local `memory/skills.json` (discovered exploits, working commands) and `memory/targets.json` (open ports, service versions). Simple JSON is sufficient — no vector database needed for a bounded simulation. Agents load this at startup and append to it after each turn. |

**Do NOT use:** Vector databases (Chroma, Weaviate) — the simulation's knowledge base is small and bounded; semantic search adds latency and complexity with no benefit. Redis for memory — another service to manage.

---

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `python-dotenv` | 1.x | Environment variable management | Load KoboldCpp URL, SSH credentials, game parameters from `.env`. Never hardcode. |
| `tenacity` | 8.x | Retry logic for LLM calls and SSH commands | K80 inference is slow; LLM calls may time out. Paramiko SSH may drop. Wrap both with exponential backoff. |
| `structlog` | 24.x | Structured logging for agent actions | Every command, LLM call, and game event needs a structured log entry for replay. `structlog` outputs clean JSON lines that SQLite can ingest. |
| `pytest` | 8.x | Unit and integration tests | Test scoring logic, tool wrappers, state machine transitions. 80% coverage on non-LLM code. |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Agent framework | LangGraph | CrewAI | CrewAI's role-playing model is not deterministic enough for replay; LangGraph's explicit graph is auditable |
| Agent framework | LangGraph | AutoGen | AutoGen's async conversation model adds complexity; overkill for 2-agent competition |
| Inference server | KoboldCpp | Ollama | Ollama does not support K80 (CUDA 3.7 too old) |
| Inference server | KoboldCpp | vLLM | vLLM requires CUDA 8.0+; K80 is 3.7 |
| Command execution | Paramiko SSH | `docker exec` | `docker exec` breaks simulation realism and is a container escape risk |
| Command execution | Paramiko SSH | `fabric` | fabric wraps Paramiko with extra abstraction not needed here |
| Orchestration | Docker Compose | Kubernetes | Kubernetes is far too heavy for a 5-container capstone demo |
| Scoring display | Rich terminal | React dashboard | Web dashboard adds frontend build complexity; terminal display is faster to ship |
| Agent memory | JSON files | ChromaDB | Vector search is unnecessary for a bounded, domain-specific memory store |
| LLM model | Gemma 4 E4B | Gemma 4 31B Dense | 31B dense won't fit in 24GB K80 VRAM even at Q4; E4B fits and runs faster |

---

## Installation

```bash
# Core agent framework
pip install langgraph langchain-core langchain-openai

# Command execution
pip install paramiko docker

# Web / scoring
pip install fastapi uvicorn[standard] aiosqlite pydantic

# Developer experience
pip install python-dotenv tenacity structlog rich

# Testing
pip install pytest pytest-asyncio

# KoboldCpp (on the inference host, not in containers)
# Download from: https://github.com/LostRuins/koboldcpp/releases
# Run: ./koboldcpp --model gemma-4-e4b-q4_k_m.gguf --usecublas --gpulayers 99 --port 5001
```

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| LangGraph as agent framework | HIGH | Context7-verifiable, widely deployed for cybersecurity agents per multiple 2025-2026 sources |
| KoboldCpp for K80 inference | MEDIUM | KoboldCpp K80 compatibility confirmed via CUDA 3.7 support in llama.cpp backend; exact token/sec on K80 with Gemma 4 E4B not benchmarked — needs empirical validation |
| Gemma 4 E4B model fit | MEDIUM | Q4_K_M quantization of E4B estimated ~5-8GB VRAM; needs empirical VRAM measurement before assuming two simultaneous agents |
| Paramiko for SSH execution | HIGH | Mature library, standard pattern for Python-based remote command execution |
| Docker Compose orchestration | HIGH | Industry standard for multi-container local development; CTF/simulation pattern well established |
| Rich terminal dashboard | HIGH | Stable library, straightforward for simulation display |
| JSON memory (not vector DB) | HIGH | Appropriate scope decision for bounded simulation |

---

## Critical Open Questions

1. **K80 VRAM validation:** Run `nvidia-smi` and load Gemma 4 E4B Q4_K_M in KoboldCpp to verify actual VRAM usage before committing to having two agent processes. If VRAM is tight, both agents share one KoboldCpp process (sequential turns, not parallel).

2. **KoboldCpp CUDA 3.7 build:** Confirm the KoboldCpp release binary is compiled with sm_37 support, or build from source with `-DLLAMA_CUDA_F16=OFF` flag. The pre-built binary targets may assume sm_75+.

3. **Gemma 4 tool-call format:** Verify KoboldCpp correctly parses Gemma 4's native function-calling format. If not, use `langchain-openai` structured output mode via JSON schema instead of native tool calls — this is a known workaround for local inference servers.

4. **Battleground VM persistence:** Decide whether the battleground resets between phases (clean Docker image) or accumulates state. Reset-on-phase-start is simpler and more reproducible for presentation.

---

## Sources

- LangGraph cybersecurity agent pattern: [Building a Cybersecurity Agent with LangGraph](https://medium.com/@rmsanjiv/building-a-cybersecurity-agent-with-langgraph-a-step-by-step-guide-cef4721bbb43)
- KoboldCpp OpenAI-compatible API: [KoboldAI LangChain Integration](https://python.langchain.com/v0.2/docs/integrations/llms/koboldai/)
- KoboldCpp releases and Gemma 4 support: [LostRuins/koboldcpp releases](https://github.com/LostRuins/koboldcpp/releases)
- Gemma 4 model family and licensing: [Google Gemma 4 overview](https://ai.google.dev/gemma/docs/core)
- Gemma 4 GGUF quantization (Unsloth): [unsloth/gemma-4-E4B-it-GGUF](https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF)
- Gemma 4 for pentesting comparison: [Gemma 4 vs Qwen for AI Pentesting](https://www.penligent.ai/hackinglabs/gemma-4-vs-qwen-for-ai-pentesting/)
- PentAGI reference architecture (autonomous pentesting agents): [vxcontrol/pentagi](https://github.com/vxcontrol/pentagi)
- Docker sandbox AI agent isolation: [Docker Sandboxes docs](https://docs.docker.com/ai/sandboxes/)
- Awesome cybersecurity agentic AI: [raphabot/awesome-cybersecurity-agentic-ai](https://github.com/raphabot/awesome-cybersecurity-agentic-ai)
- Top open-source AI pentesting projects: [spark42.tech top 10](https://blog.spark42.tech/top-10-open-source-ai-agent-penetration-testing-projects/)
