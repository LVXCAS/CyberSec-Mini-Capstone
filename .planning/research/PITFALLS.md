# Domain Pitfalls: Autonomous Cybersecurity AI Agent Simulation

**Domain:** Autonomous AI agents executing real shell commands in a competitive red-vs-blue cybersecurity simulation
**Researched:** 2026-04-08
**Project context:** Two Gemma 4 (e2b/e4b) instances on a single 24GB K80 GPU via Kobalt, attacking/defending a shared Ubuntu battleground VM

---

## Critical Pitfalls

Mistakes that cause rewrites, demo failures, or unsafe execution.

---

### Pitfall 1: Two Model Instances Exceeding K80 VRAM Mid-Inference

**What goes wrong:** Both agents start their inference turns simultaneously. The KV cache grows as context builds — a model that loaded cleanly at 8–10 GB can spike to 16+ GB under long context or complex reasoning. With two instances sharing 24 GB, mid-inference OOM crashes one or both agents without warning.

**Why it happens:** VRAM requirements have three components: model weights (fixed), KV cache (grows with context length), and runtime overhead. Most teams budget only for weights. Two 4B instances at Q4 quantization weigh ~5 GB each — that looks safe at 10 GB total, but the KV cache alone can double memory consumption during long turns.

**Consequences:** One agent crashes silently mid-turn. The game continues with an unresponsive agent, producing no output, which the scoring system may misinterpret. Demo halts.

**Warning signs:**
- Agent response times grow longer over successive turns (KV cache filling)
- `nvidia-smi` showing VRAM near ceiling between turns
- Kobalt inference server returning OOM errors with no obvious trigger

**Prevention:**
- Enforce a hard maximum context window per agent turn (e.g., 2048 tokens input + 512 tokens output max)
- Stagger inference: do not allow both agents to run inference simultaneously. Use a token budget or turn queue so only one model is generating tokens at a time.
- Benchmark VRAM at max context before the demo — not just at load time
- Reserve at minimum 2–3 GB headroom above combined model weights for KV cache
- If using quantization: Q4 reduces weight size but also increases hallucination rate — test command quality at the quantization level you deploy

**Phase to address:** Infrastructure / GPU allocation phase (before any agent logic)

---

### Pitfall 2: Gemma 4 Hallucinating Shell Commands That Look Valid but Aren't

**What goes wrong:** Small models (2B–4B) generate syntactically plausible shell commands that reference tools not installed, flags that don't exist, or paths that aren't present on the battleground VM. The command runs, errors silently or loudly, and the agent either loops or moves on with a false belief state.

**Why it happens:** Quantized small models exhibit significantly higher "package hallucination rates" than full-precision larger models. A 4-bit model may confidently generate `nmap --script vuln --host-scan TARGET` where `--host-scan` is not a valid nmap flag. The model has no feedback that the command failed unless the error output is explicitly returned in its next prompt.

**Consequences:** Agent wastes turns issuing bad commands. If errors aren't fed back, the agent builds a false belief about what it accomplished (e.g., believes it ran a port scan when it didn't). Red agent hallucinates exploits that require tools not present. Blue agent hallucinates firewall rules that were never applied.

**Warning signs:**
- Command output contains "command not found", "invalid option", or "no such file"
- Agent continues as if the command succeeded despite an error in stdout
- Same hallucinated command repeated across multiple turns

**Prevention:**
- Always return the last N lines of stdout/stderr to the agent's next prompt — never discard command output
- Parse exit codes: treat non-zero exit as explicit failure, force the agent to acknowledge it in the next prompt
- Pre-install all expected tools on battleground VM; don't rely on agents to install dependencies mid-game
- Build a command validator that blocks obviously malformed commands before execution (simple regex or a whitelist of known-good tool names)
- Maintain a short "action log" in each agent's context summarizing what succeeded and what failed

**Phase to address:** Agent execution loop phase

---

### Pitfall 3: Agent Entering an Infinite Retry Loop

**What goes wrong:** An agent fails to accomplish a goal (e.g., cannot gain access, firewall blocks the port). Rather than pivoting strategy, it retries the same command — or minor variations — indefinitely. Because the LLM reasons locally ("this should work, let me try again"), it does not recognize it is looping.

**Why it happens:** LLMs have no implicit memory of their action history within a session unless that history is in their context window. A model that fails on turn 3 and turn 7 will attempt the same approach on turn 11 because each decision is probabilistic and contextually plausible, not logically aware of repetition.

**Consequences:** One agent consumes all available game time on futile retries. Scoring snapshots capture no progress. Demo appears broken or stalled.

**Warning signs:**
- Same command string appearing more than twice in agent's action log
- No change in scoring metrics across 3+ consecutive snapshots
- Agent context grows without any new successful actions

**Prevention:**
- Hard turn limit per game phase: if an agent exceeds N turns without a successful action, force a "strategic reassessment" prompt
- Deduplication check: before executing any command, compare it against the last 5 commands issued. If it matches, inject a "You have already tried this — choose a different approach" system message.
- Track unique successful actions, not just total turns, in the scoring heartbeat
- Add a "moves since last progress" counter; trigger a forced re-prompt when it hits 3

**Phase to address:** Agent execution loop phase

---

### Pitfall 4: Docker Isolation Failing — Agent Escaping to Host or Wrong Container

**What goes wrong:** A misconfigured Docker network, a mounted socket, or an exposed API endpoint allows an agent (or the commands it executes) to affect the host system or the wrong container. In a red-vs-blue scenario this is doubly dangerous: red agent commands intended for the battleground VM reach the blue agent VM or the host running the inference server.

**Why it happens:** Common misconfigurations include: mounting `/var/run/docker.sock` into any container (gives full Docker daemon control), using `network_mode: host` for convenience, or binding inference ports to `0.0.0.0` instead of `127.0.0.1`. CVE-2025-9074 (CVSS 9.3) demonstrated that Docker Desktop versions below 4.44.3 could allow container-to-host API access without authentication.

**Consequences:** Red agent commands execute on the inference server rather than the battleground VM. Blue agent actions interfere with red agent infrastructure. Worst case: battleground VM commands reach the host and persist across game resets — breaking the "fresh Ubuntu" guarantee.

**Warning signs:**
- Command side effects visible outside expected container scope
- Game reset ("new game with one command") doesn't fully restore battleground state
- Agent logs show access to paths that shouldn't exist on the battleground

**Prevention:**
- Never mount `/var/run/docker.sock` into agent containers or the battleground VM
- Use an explicit Docker network (`--network cyber-game-net`) with no host passthrough
- Bind inference APIs to `127.0.0.1` only, not all interfaces
- Use read-only mounts where write access isn't needed
- Verify Docker Desktop version is >= 4.44.3 or use Docker Engine on Linux
- Test game reset: after a game, confirm the battleground VM has reverted completely (no files written by agents persist)
- Assign distinct container names and verify agent commands are routed to the correct target container via an explicit intermediary (never let agents directly address containers by IP)

**Phase to address:** Infrastructure / Docker networking phase

---

### Pitfall 5: Scoring Race Conditions During Simultaneous Battle Phase

**What goes wrong:** Both agents act simultaneously. A scoring snapshot runs at second 30, capturing partial state: red has opened a port but hasn't yet used it; blue has detected something but hasn't yet blocked it. The snapshot awards points incorrectly, or worse, one agent's action resolves between the snapshot and the next tick, creating a scoring gap.

**Why it happens:** Scoring based on system state snapshots (e.g., "is port X open?", "is this file present?") is vulnerable to timing: actions take real time to execute, and the snapshot may observe intermediate states. Additionally, if both agents can write to shared log or scoring files simultaneously, file corruption or partial writes occur.

**Consequences:** Scores don't reflect actual game outcomes. Blue agent gets no credit for a block that took 2 seconds to apply but was checked at second 1. Red agent scores persistence on a file it wrote and blue immediately deleted, but both actions happened between snapshots.

**Warning signs:**
- Scoring results that seem inconsistent with observable game state
- Scores fluctuating up and down across consecutive snapshots for the same category
- Log files with interleaved or partial writes

**Prevention:**
- Score actions (events), not just state snapshots — log each agent action with a timestamp and award points when the action is confirmed complete, not when the snapshot runs
- Use append-only event logs (one file per agent) — never share a log file between agents
- Apply file locking or use a lightweight message queue for scoring updates
- Make snapshot intervals longer than the maximum expected command execution time (if commands take up to 10 seconds, don't snapshot every 5)
- Include a "settling delay" of 2–3 seconds after each agent action batch before capturing the scoring snapshot

**Phase to address:** Scoring system phase

---

### Pitfall 6: Fresh Battleground Guarantee Breaking on Game Reset

**What goes wrong:** The replayability requirement ("start a new game with one command") relies on the battleground VM resetting to a clean state. If Docker volumes aren't properly cleared, or if the blue agent wrote system-level configurations that survive a container restart, the second game starts from a dirty state — blue's hardening from game 1 is still in place, making the red agent's job different each run.

**Why it happens:** `docker restart` does not wipe a container's writable layer. Only `docker rm` + `docker run` from the original image resets state. Teams commonly use restart for speed and don't notice that config files, iptables rules, and cron jobs persist.

**Consequences:** Game 2 is not equivalent to Game 1. Demo shows inconsistent behavior between runs. Scoring becomes unpredictable.

**Prevention:**
- Use `docker rm` + `docker run` (from a base image snapshot), never `docker restart`, for game resets
- Write a `reset.sh` script that destroys and recreates all game containers from fixed images
- Test the reset script 5+ times before the demo and verify battleground state is identical each time
- Commit the base image as a tagged snapshot (`battleground:clean`) so resets are always from a known-good baseline
- Do not use persistent Docker volumes for any battleground VM data

**Phase to address:** Infrastructure / replayability phase

---

## Moderate Pitfalls

Mistakes that cause delays, bad demos, or scoring unfairness.

---

### Pitfall 7: Agent Context Growing Until Performance Degrades

**What goes wrong:** Each agent accumulates a growing context window across turns. By turn 20, the context may contain the full history of every command and output. Inference time per turn grows. The model also "loses focus" on early context — effective attention degrades on long contexts, making the agent less coherent in strategy.

**Prevention:**
- Implement a rolling context window: keep the last N=8–10 turns + a persistent "strategy summary" prepended each turn
- Summarize completed phases into a short paragraph ("Blue phase: blocked ports 21, 23, 3306. Installed fail2ban.") before discarding their full history
- Set a hard token budget per agent turn and truncate from the oldest end if exceeded

**Phase to address:** Agent memory design phase

---

### Pitfall 8: Blue Agent Hardening Itself Into a Corner (Self-Lockout)

**What goes wrong:** The blue agent, trying to harden the battleground VM, applies firewall rules that block the control plane — the very connection the orchestrator uses to issue commands or check status. Blue locks out the game system from the battleground.

**Prevention:**
- Maintain a protected allowlist of IPs/ports that blue agent is never permitted to block (orchestrator IP, scoring port, SSH from control host)
- Enforce this allowlist at the executor level, not in the prompt — the model cannot be trusted to reliably honor it
- Test blue agent hardening in isolation before running the full game

**Phase to address:** Blue agent logic phase

---

### Pitfall 9: Red Agent Commands Executing on the Wrong Target

**What goes wrong:** The red agent generates a command intended for the battleground VM but it executes on the red agent VM or the orchestrator. This can happen if the command routing layer (SSH, Docker exec) is misconfigured or if the agent generates a command targeting `localhost` without knowing which host is "local."

**Prevention:**
- All agent-generated commands must pass through an explicit routing layer that prepends the correct target (`docker exec battleground <cmd>` or SSH to the correct IP)
- Never allow agents to issue commands directly to a shell — always mediate through an executor service that enforces targeting
- Log the actual target alongside every command for auditability

**Phase to address:** Command execution layer phase

---

### Pitfall 10: Decision Log Becoming Unreadable for Demo Purposes

**What goes wrong:** The decision log captures raw LLM output, including verbose reasoning chains, JSON artifacts, error messages, and repeated failed attempts. During demo playback, the log is too dense to communicate what happened. Judges see noise, not insight.

**Prevention:**
- Separate raw agent logs (for debugging) from the curated decision log (for demo display)
- The curated log should contain: agent name, turn number, action taken (one line), outcome (one line), reasoning summary (2–3 sentences max)
- Build the curated log format early; it is harder to retrofit than to design upfront

**Phase to address:** Logging and display phase

---

## Minor Pitfalls

---

### Pitfall 11: Kobalt API Behavior Differences vs. Ollama

**What goes wrong:** Documentation, examples, and community knowledge for local LLM inference almost universally assume Ollama. Kobalt may differ in: how system prompts are handled, whether stop tokens work as expected, how concurrent requests are queued, and how errors surface.

**Prevention:**
- Treat Kobalt as a black box and test all agent prompt patterns against it directly — do not assume Ollama behavior transfers
- Specifically test: concurrent request handling (two agents at once), timeout behavior, error response format
- Build a thin wrapper that normalizes Kobalt's API responses to a consistent internal format so the agent logic is decoupled from inference server specifics

**Phase to address:** Infrastructure / Kobalt integration phase

---

### Pitfall 12: Gemma 4 e2b Reasoning Quality Insufficient for Autonomous Strategy

**What goes wrong:** Gemma 4 e2b (2B params) may not produce coherent multi-step attack/defense strategies. It may execute single valid commands but fail to chain them into a meaningful kill chain or defense posture. The agent takes valid actions with no strategic coherence.

**Prevention:**
- Test both e2b and e4b with realistic game prompts before committing to a model size
- Design prompts that provide explicit strategic scaffolding ("Your current objective is X. Your last three actions were Y. What is your next action to advance toward X?") rather than open-ended "what do you do next?"
- If e2b is too weak, confirm whether e4b fits two instances on 24 GB at the chosen quantization level before the demo

**Phase to address:** Model selection and prompt engineering phase

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|---|---|---|
| GPU / Kobalt setup | Two instances OOM during simultaneous inference | Stagger inference, benchmark KV cache at max context |
| Docker networking | Container escape or wrong-target command routing | Explicit networks, no docker.sock mounts, executor routing layer |
| Agent execution loop | Infinite retry loops, hallucinated commands | Turn limits, deduplication, always return stdout/stderr |
| Blue agent setup phase | Self-lockout via aggressive firewall rules | Hardcoded allowlist enforced at executor level |
| Battle phase simultaneous play | Scoring race conditions | Event-based scoring + settling delays |
| Game reset / replayability | Dirty battleground state | `docker rm` + `docker run` from tagged image, test 5x |
| Decision log / demo display | Raw logs unreadable during presentation | Build curated log format from day one |
| Model quality | e2b too weak for coherent strategy | Test both sizes with real game prompts before committing |

---

## Sources

- [How Do LLMs Fail In Agentic Scenarios? (arXiv 2512.07497)](https://arxiv.org/pdf/2512.07497) — agent failure mode taxonomy
- [Secure or Suspect? Investigating Package Hallucinations of Shell Commands in Quantized LLMs (arXiv 2512.08213)](https://arxiv.org/html/2512.08213) — quantization increases hallucination rate
- [GPU Survival Guide: Avoid OOM Crashes for Large Models (RunPod)](https://www.runpod.io/articles/guides/avoid-oom-crashes-for-large-models) — KV cache as hidden OOM cause
- [Running Multiple Local Models: Memory Management Strategies (SitePoint)](https://www.sitepoint.com/running-multiple-local-models-memory-management-strategies/) — multi-instance VRAM planning
- [Why AI Agents Get Stuck in Loops, and How to Prevent It](https://www.fixbrokenaiapps.com/blog/ai-agents-infinite-loops) — loop detection and prevention
- [LLM Tool-Calling in Production: The Infinite Loop Failure Mode](https://medium.com/@komalbaparmar007/llm-tool-calling-in-production-rate-limits-retries-and-the-infinite-loop-failure-mode-you-must-2a1e2a1e84c8) — retry loop mechanics
- [CVE-2025-9074: Critical Docker Desktop Container Escape (Rescana)](https://www.rescana.com/post/cve-2025-9074-critical-docker-desktop-container-escape-vulnerability-cvss-9-3-analysis-and-miti) — Docker isolation failure vectors
- [Docker & Kubernetes Vulnerabilities 2025–2026 (KLEAP/Medium)](https://learnkiis.medium.com/docker-kubernetes-vulnerabilities-securing-containers-in-2025-2026-76628c1fc2c3) — container security landscape
- [Stateful vs Stateless AI Agents: Architecture Guide (Tacnode)](https://tacnode.io/post/stateful-vs-stateless-ai-agents-practical-architecture-guide-for-developers) — context window and memory design
- [AI Agents: Reliability Challenges & Proven Solutions 2026 (Edstellar)](https://www.edstellar.com/blog/ai-agent-reliability-challenges) — production reliability gaps
- [Gemma 4 and LLM Ops: VRAM Management (n1n.ai)](https://explore.n1n.ai/blog/gemma-4-llm-ops-fine-tuning-vram-management-2026-04-04) — Gemma 4 specific VRAM guidance
