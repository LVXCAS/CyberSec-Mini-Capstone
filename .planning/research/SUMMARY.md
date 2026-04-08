# Project Research Summary

**Project:** Autonomous Cybersecurity AI Agents (Red vs. Blue Simulation)
**Domain:** Multi-agent adversarial AI simulation on live infrastructure
**Researched:** 2026-04-08
**Confidence:** MEDIUM-HIGH

## Executive Summary

This project is a capstone-scale autonomous red-vs-blue cybersecurity simulation where two LLM-powered agents independently attack and defend a live Ubuntu VM. Experts in this domain consistently converge on a hub-and-spoke orchestrator pattern: agents never touch the battleground directly, all execution is proxied through a central orchestrator that enforces safety, logs decisions, and manages phase state. The simulation runs on a single 24GB K80 GPU using Gemma 4 E4B (Q4_K_M quantization) served via KoboldCpp — a constrained but workable hardware setup that demands sequential inference and strict context budgeting. LangGraph is the clear choice for agent logic, providing explicit, auditable state graphs appropriate for the observe-plan-act loop that cybersecurity agents require.

The recommended approach is to build in six layers, each testable independently before the next is added: infrastructure and networking first, orchestrator core second, a single agent loop third, scoring fourth, dual-agent simultaneous play fifth, and presentation polish last. This order is dictated by hard dependencies — nothing can be tested without a running inference server and battleground VM, and two-agent coordination complexity should only be introduced after single-agent execution is proven solid. The critical differentiating features (reasoning trace display, persona framing, replay mode) are low-to-medium complexity add-ons that require the core loop to be stable first.

The primary risks are hardware-driven: the K80's 24GB VRAM must be validated empirically before committing to any two-instance inference plan, KV cache growth mid-inference can OOM silently, and the K80's CUDA 3.7 compute capability eliminates Ollama and vLLM as alternatives. The secondary risks are simulation integrity risks: agent infinite loops, command hallucinations, Docker isolation failures, and scoring race conditions each have known mitigations but must be addressed from the start of implementation, not retrofitted.

## Key Findings

### Recommended Stack

The stack is Python-first throughout. LangGraph (0.2.x+) provides the agent state machine; KoboldCpp running Gemma 4 E4B at Q4_K_M quantization provides local inference on the K80; `langchain-openai` connects agents to KoboldCpp via its OpenAI-compatible endpoint. Command execution from agent logic to the battleground VM goes through Paramiko SSH — realistic, auditable, and isolated. The orchestrator is FastAPI. The scoring persistence layer is SQLite. Terminal display uses the Rich library. Docker Compose v2 manages the 5-container topology.

**Core technologies:**
- **LangGraph 0.2.x+**: Agent state machine and tool routing — explicit graph over CrewAI's opaque roles; auditable, replayable
- **KoboldCpp (1.76+)**: Local inference server — only CUDA 3.7-compatible option; wraps llama.cpp with OpenAI-compatible REST
- **Gemma 4 E4B Q4_K_M**: Agent reasoning model — MoE variant fits on K80; Apache 2.0 license; native tool-call support
- **Paramiko 3.x**: SSH-based command relay to battleground — realistic execution path; no docker.sock exposure
- **FastAPI 0.115.x**: Orchestrator API and scoring server — async, Pydantic-native, OpenAPI docs for demo
- **Docker Compose v2**: 5-container topology management — reproducible, one-command reset capability
- **Rich 13.x**: Terminal dashboard — faster to ship than a web frontend; equally compelling for capstone presentation
- **SQLite + aiosqlite**: Game log persistence — zero-dependency, file-based, sufficient for bounded simulation

**Do not use:** Ollama (no K80 support), vLLM (requires CUDA 8.0+), CrewAI (hides state), `docker exec` for agent commands (breaks simulation realism and isolation).

### Expected Features

The simulation requires a tight core loop before any differentiating features are layered on. Missing any table-stakes feature makes the simulation fundamentally non-functional or unsafe.

**Must have (table stakes):**
- Shell command execution with allowlist + timeout — core mechanic; agents must act in the environment
- Sequential reasoning loop (observe → plan → act → reflect) — without it, agents fire commands randomly
- Working memory / context window management — K80 + Gemma 4 will hit context limits fast; must be designed from day one
- Action log and decision log (reasoning trace) — minimum audit trail and the AI dimension that differentiates from scripted tools
- Phase state machine (SETUP → BATTLE → SCORING) with timers and win/loss detection — defines the game
- Points-based scoring with final summary — makes the outcome legible to a non-technical audience
- Command allowlist/denylist and agent sandbox enforcement — without this, an agent can destroy the host OS
- Emergency kill switch — manual override; agents will hang or loop

**Should have (differentiators):**
- Agent persona framing (red as APT, blue as SOC) — high presentation value, low implementation cost
- VM snapshot/reset for replayability — one-command reset is critical for capstone demos
- Side-by-side reasoning trace display — makes the AI reasoning dimension visible to judges
- Replay mode — present an interesting run multiple times without re-running the slow model
- Self-assessment / reflection step — agent evaluates whether last action worked before choosing next

**Defer to post-MVP:**
- Live web dashboard — high complexity; Rich terminal dashboard achieves the same goal faster
- MITRE ATT&CK tagging — impressive but non-functional for the simulation itself
- Honeypot deployment by blue team — second-priority differentiator
- Weighted scoring multipliers
- Multiple scenario YAML configs
- Lateral movement / multi-node topology — out of scope for single K80 hardware

### Architecture Approach

The architecture is a hub-and-spoke model with the orchestrator as the central safety and coordination layer. Agent processes on separate VMs communicate only with the orchestrator — never with the battleground VM directly and never with each other. The orchestrator proxies all commands through its safety filter before SSH relay to the battleground, eliminating an entire class of sandbox escape and cross-agent contamination risks. The KoboldCpp inference server is shared by both agents with sequential queuing, which is the only safe option given 24GB VRAM constraints.

**Major components:**
1. **Agent Process (Red / Blue)** — Autonomous decision loop: perception, LLM reasoning (via Kobalt), command submission, memory update
2. **Orchestrator** — Game master: phase state machine, command relay + safety filter, observation builder, scoring engine, decision log writer, end condition monitor
3. **Battleground VM** — Passive execution target: receives all commands relayed by orchestrator; fully replaceable from Docker image snapshot
4. **KoboldCpp Inference Server** — Shared LLM backend: serves Gemma 4 to both agents sequentially via OpenAI-compatible REST
5. **Scoring Engine** — Reads battleground state independently via SSH; ground truth never comes from agent self-reports

### Critical Pitfalls

1. **K80 VRAM OOM during simultaneous inference** — Model weights alone look safe (2x ~5GB = 10GB) but KV cache growth mid-inference can push combined usage above 20GB. Mitigation: enforce a hard max context per turn (2048 tokens input + 512 output), stagger inference so only one agent generates at a time, benchmark VRAM at max context before the demo — not just at load time.

2. **Gemma 4 hallucinating shell commands** — Quantized small models generate syntactically plausible but invalid commands; the agent builds a false belief if errors aren't fed back. Mitigation: always return last N lines of stdout/stderr to the agent's next prompt; parse exit codes and treat non-zero as explicit failure; pre-install all expected tools on the battleground VM.

3. **Agent infinite retry loops** — LLMs without explicit history may retry the same failed command indefinitely. Mitigation: hard turn limit per phase; deduplication check against last 5 commands; "moves since last progress" counter that triggers a forced re-prompt at 3.

4. **Docker isolation failure** — Mounting `/var/run/docker.sock`, using `network_mode: host`, or binding APIs to `0.0.0.0` can allow agent commands to reach the wrong container or the host. Mitigation: never mount docker.sock into agent containers; use explicit Docker bridge networks; bind inference APIs to 127.0.0.1; verify Docker Desktop >= 4.44.3.

5. **Fresh battleground guarantee breaking on reset** — `docker restart` does not wipe the container's writable layer; game 2 starts from dirty state. Mitigation: use `docker rm` + `docker run` from a tagged clean image (`battleground:clean`) for every reset; test the reset script 5+ times before the demo.

## Implications for Roadmap

Based on research, suggested phase structure (mirrors the build order from ARCHITECTURE.md, validated against FEATURES.md dependencies):

### Phase 1: Infrastructure Foundation
**Rationale:** Nothing can be tested without a running inference server, a reachable battleground VM, and working Docker networking. This is the prerequisite for every other layer.
**Delivers:** KoboldCpp running Gemma 4 E4B on K80; battleground Ubuntu container with SSH accessible from orchestrator host; Docker Compose topology with isolated bridge networks; empirical VRAM benchmark confirming headroom for sequential dual-agent inference.
**Addresses:** Table-stakes safety (network isolation, no docker.sock mounts); K80 compatibility validation
**Avoids:** Pitfall 1 (VRAM OOM), Pitfall 4 (Docker isolation failure), Pitfall 11 (Kobalt API assumptions)

### Phase 2: Orchestrator Core
**Rationale:** The orchestrator is the central hub — agents and scoring both depend on it. Build and validate it with stub clients before any real agent logic is introduced.
**Delivers:** Phase state machine (SETUP → BATTLE → CONCLUSION); command relay accepting POST and SSH-executing on battleground; safety filter (blocklist + role-based allowlist); decision log writer (JSONL append-only)
**Uses:** FastAPI, Paramiko, SQLite, structlog
**Implements:** Orchestrator component from ARCHITECTURE.md
**Avoids:** Pitfall 5 (scoring race conditions — event log designed from the start), Pitfall 10 (curated decision log format built upfront)

### Phase 3: Single Agent Execution Loop
**Rationale:** Most bugs live in the LLM-to-execution path. Test the full path with one agent before introducing the second agent's coordination complexity.
**Delivers:** One agent process (LangGraph ReAct loop) connected to real Kobalt and real orchestrator; rolling context window; short-term memory; agent submits commands, receives observations, updates memory; 3-5 autonomous turns on the battleground
**Uses:** LangGraph, langchain-openai, Paramiko (via orchestrator), Pydantic v2, tenacity (LLM retry)
**Implements:** Agent Process component from ARCHITECTURE.md
**Avoids:** Pitfall 2 (command hallucinations — stdout/stderr feedback wired in), Pitfall 3 (infinite loops — turn limit and dedup from day one), Pitfall 7 (context growth — rolling window implemented here)

### Phase 4: Scoring Engine
**Rationale:** Scoring reads battleground state (Phase 1 required) and integrates with the orchestrator (Phase 2 required). Agents (Phase 3) produce events scoring evaluates. Must come before dual-agent play.
**Delivers:** Battleground state snapshot script (open ports, running services, file presence); score computation mapping snapshot diffs to point categories; score log (JSONL); final score summary output
**Uses:** Paramiko (battleground SSH read), SQLite, Pydantic v2 for ScoreCard models
**Implements:** Scoring Engine sub-component of Orchestrator
**Avoids:** Pitfall 5 (race conditions — event-based scoring with settling delays, not pure snapshot scoring)

### Phase 5: Dual-Agent Full Game
**Rationale:** Two-agent coordination (Kobalt queue contention, interleaved battleground state, simultaneous command requests) is introduced only after single-agent execution is proven solid.
**Delivers:** Red and blue agent processes running simultaneously; orchestrator handles interleaved command requests; end condition monitor (time expiry, kill chain completion, blue lockout); full game runs from start to scored conclusion
**Implements:** Both Agent Process instances + End Condition Monitor from ARCHITECTURE.md
**Avoids:** Pitfall 1 (sequential inference enforced — only one agent generates at a time), Pitfall 8 (blue self-lockout — orchestrator allowlist enforced at executor level, not in prompt), Pitfall 9 (wrong-target routing — explicit routing layer logs actual target alongside every command)

### Phase 6: Replayability and Presentation Polish
**Rationale:** Polish after correctness. The demo-facing layer is only meaningful if the simulation underneath works.
**Delivers:** `reset.sh` using `docker rm` + `docker run` from `battleground:clean` image; agent persona system prompts (APT / SOC framing); side-by-side curated decision log display (Rich terminal); replay mode (log-driven re-execution with delays); README with demo instructions; safety filter hardened to full allowlist
**Avoids:** Pitfall 6 (dirty battleground on reset — tested 5+ times before demo)

### Phase Ordering Rationale

- Infrastructure must be Phase 1 because every other component depends on the inference server and battleground VM being reachable.
- Orchestrator before agents because agents communicate through it — an agent built first would need to be rewired to the orchestrator later.
- Single agent before dual agent because Kobalt queue contention, interleaved state, and coordination bugs are invisible with one agent and immediately apparent with two.
- Scoring before dual agent because dual-agent play without scoring produces no legible output.
- Polish last because presentation layer built on a broken simulation wastes time.
- This ordering also naturally surfaces the two most critical open questions (K80 VRAM and Kobalt CUDA 3.7 compatibility) in Phase 1, where they can be resolved before significant development investment.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1 (Infrastructure):** KoboldCpp CUDA 3.7 build verification and Gemma 4 tool-call format compatibility with KoboldCpp need empirical validation — sparse documentation exists; test before committing.
- **Phase 3 (Agent Loop):** Prompt engineering for Gemma 4 E4B at Q4_K_M quantization for cybersecurity tool use is not well-documented; expect iteration. Test both E2B and E4B with real game prompts before committing to model size.
- **Phase 5 (Dual Agent):** Kobalt concurrent request handling behavior under load is untested in this configuration — test concurrent POST behavior specifically.

Phases with standard patterns (skip research-phase):
- **Phase 2 (Orchestrator):** FastAPI + Paramiko + SQLite is a well-documented pattern; orchestrator design is clearly specified in ARCHITECTURE.md.
- **Phase 4 (Scoring):** Scoring from SSH-read system state is straightforward; event-log pattern is well established.
- **Phase 6 (Polish):** Docker reset script, Rich terminal layout, and system prompt persona framing are all standard techniques.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | LangGraph, Paramiko, FastAPI, Docker Compose are HIGH confidence. KoboldCpp on K80 and Gemma 4 E4B VRAM fit are MEDIUM — confirmed plausible, not empirically benchmarked on this exact hardware. |
| Features | MEDIUM-HIGH | Table stakes derived from multiple sources (PentAGI, CyberBattleSim, academic surveys). No single canonical spec for this exact simulation format. |
| Architecture | HIGH | Hub-and-spoke orchestrator pattern appears consistently across CybORG++, HackSynth, PentAGI, and OWASP AI Agent Security. Component boundaries and data flow are well-established. |
| Pitfalls | HIGH | VRAM OOM, command hallucination, infinite loops, and Docker isolation failures are documented failure modes with empirical backing (CVE-2025-9074, arXiv hallucination studies, RunPod GPU guides). |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **K80 VRAM empirical validation:** Run `nvidia-smi` and load Gemma 4 E4B Q4_K_M in KoboldCpp, then generate a max-context response. Measure peak VRAM. This is the single most important validation before any development. If VRAM is tight, one KoboldCpp process serves both agents sequentially — the architecture accommodates this.
- **KoboldCpp CUDA 3.7 binary compatibility:** Confirm the KoboldCpp release binary compiles with sm_37, or build from source. Pre-built binaries may target sm_75+. Must be validated in Phase 1.
- **Gemma 4 tool-call format via KoboldCpp:** Verify KoboldCpp correctly passes Gemma 4 native function-calling tokens. If not, use `langchain-openai` structured JSON output mode as a fallback. Validate in Phase 1 before the agent loop is built.
- **E2B vs E4B quality decision:** Both model sizes need real game-prompt testing before Phase 3 is committed. E2B may be too weak for coherent multi-step strategy; E4B needs confirmed VRAM headroom.
- **Battleground VM reset speed:** If `docker rm` + `docker run` takes more than 30 seconds, demo pacing is affected. Validate reset time and optimize the base image if needed.

## Sources

### Primary (HIGH confidence)
- [LangGraph cybersecurity agent pattern](https://medium.com/@rmsanjiv/building-a-cybersecurity-agent-with-langgraph-a-step-by-step-guide-cef4721bbb43) — LangGraph for cybersecurity ReAct loops
- [PentAGI reference architecture](https://github.com/vxcontrol/pentagi) — modular orchestrator + sandboxed executor
- [CybORG++ architecture](https://arxiv.org/html/2410.16324v1) — agent/environment separation patterns
- [HackSynth](https://arxiv.org/html/2412.01778v1) — Planner + Summarizer pattern for hacking agents
- [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html) — execution isolation, memory poisoning defense
- [ISOLATEGPT](https://cybersecurity.seas.wustl.edu/paper/wu2025isolate.pdf) — hub-and-spoke isolation pattern

### Secondary (MEDIUM confidence)
- [KoboldCpp releases and Gemma 4 support](https://github.com/LostRuins/koboldcpp/releases) — CUDA compatibility scope
- [Gemma 4 GGUF quantization via Unsloth](https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF) — quantization levels and VRAM estimates
- [Gemma 4 for pentesting comparison](https://www.penligent.ai/hackinglabs/gemma-4-vs-qwen-for-ai-pentesting/) — model quality for cybersecurity tasks
- [GPU OOM survival guide (RunPod)](https://www.runpod.io/articles/guides/avoid-oom-crashes-for-large-models) — KV cache as hidden OOM cause
- [LLM agent failure modes (arXiv 2512.07497)](https://arxiv.org/pdf/2512.07497) — infinite loops and hallucination taxonomy
- [Package hallucinations in quantized LLMs (arXiv 2512.08213)](https://arxiv.org/html/2512.08213) — quantization increases hallucination rate
- [CVE-2025-9074 Docker Desktop escape](https://www.rescana.com/post/cve-2025-9074-critical-docker-desktop-container-escape-vulnerability-cvss-9-3-analysis-and-miti) — Docker isolation failure vectors
- [Autonomous Red vs Blue Teaming — ISACA 2026](https://www.isaca.org/resources/news-and-trends/industry-news/2026/autonomous-red-vs-blue-teaming-a-new-frontier-in-cybersecurity-risk-and-reward) — domain state of the art

### Tertiary (LOW confidence — needs validation)
- [Gemma 4 LLM Ops VRAM management (n1n.ai)](https://explore.n1n.ai/blog/gemma-4-llm-ops-fine-tuning-vram-management-2026-04-04) — Gemma 4 specific VRAM figures; needs empirical confirmation on K80
- [KoboldCpp OpenAI-compatible API (LangChain docs)](https://python.langchain.com/v0.2/docs/integrations/llms/koboldai/) — integration pattern documented but Gemma 4 tool-call specifics untested

---
*Research completed: 2026-04-08*
*Ready for roadmap: yes*
