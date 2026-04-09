# System Architecture

## Hub-and-Spoke Container Architecture

```mermaid
graph TB
    subgraph Host["Host Machine (GPU Server — K80 24GB)"]
        KC[KoboldCpp Inference Server<br/>Gemma 4 E4B Q4_K_M<br/>OpenAI-compatible API<br/>Port 5001]
    end

    subgraph DockerCompose["Docker Compose Environment"]
        subgraph red_net["red-net (internal, isolated)"]
            RA[red-agent<br/>Python / LangGraph<br/>observe → reason → act]
        end

        subgraph blue_net["blue-net (internal, isolated)"]
            BA[blue-agent<br/>Python / LangGraph<br/>observe → reason → act]
        end

        subgraph orchestrator_net["orchestrator-net (bridge)"]
            ORC[Orchestrator<br/>FastAPI<br/>Port 8000]
            SF[Safety Filter<br/>Blocklist Validator<br/>Command Interceptor]
            DB[(SQLite DB<br/>game_log.db<br/>scores + events)]
            BG[battleground<br/>Ubuntu 22.04<br/>Vulnerable Services<br/>SSH Port 22]
        end
    end

    RA -- "POST /execute (skill name + args)" --> ORC
    BA -- "POST /execute (skill name + args)" --> ORC
    RA -- "GET /state" --> ORC
    BA -- "GET /state" --> ORC
    RA -. "LLM inference (HTTP)" .-> KC
    BA -. "LLM inference (HTTP)" .-> KC
    ORC --> SF
    SF -- "Validated command" --> BG
    SF -- "Blocked (log only)" --> DB
    ORC -- "Score + event log" --> DB
    BG -- "Command output" --> ORC
    ORC -- "Result + new state" --> RA
    ORC -- "Result + new state" --> BA

    style red_net fill:#ffdddd,stroke:#cc0000
    style blue_net fill:#ddeeff,stroke:#0055cc
    style orchestrator_net fill:#eeffee,stroke:#006600
    style Host fill:#ffffdd,stroke:#999900
    style SF fill:#ffeecc,stroke:#cc6600
    style DB fill:#eeeeff,stroke:#6666cc
```

## Network Isolation

| Network | Members | Purpose |
|---------|---------|---------|
| `red-net` | red-agent, orchestrator | Red agent communication only |
| `blue-net` | blue-agent, orchestrator | Blue agent communication only |
| `orchestrator-net` | orchestrator, battleground | Command execution channel |

**Key constraint:** red-agent and blue-agent are on separate isolated networks. They cannot communicate with each other or with battleground directly. All traffic routes through the orchestrator.

## Data Flow

```
Agent → POST /execute {skill, args}
      → Orchestrator validates skill name
      → Safety Filter checks command against blocklist
      → SSH exec on battleground (Paramiko)
      → Output truncated to 4096 chars
      → Score awarded, event logged to SQLite
      → JSON result returned to agent
      → Agent updates LangGraph state
      → Next observe → reason → act cycle
```

## Inference Architecture

```
Agent LangGraph node (reason)
  → HTTP POST to KoboldCpp (host:5001/v1/chat/completions)
  → Gemma 4 E4B generates JSON action
  → Regex fallback parser if JSON malformed
  → Up to 3 retries with format hints
  → Sequential: only one agent infers at a time
```

KoboldCpp runs directly on the host to access the K80 GPU via CUDA 3.7. Containers reach it via `host.docker.internal`.
