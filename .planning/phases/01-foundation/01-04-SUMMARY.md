# Phase 01 Plan 04: Autonomous Agent Reasoning Loop Summary

**One-liner:** LangGraph StateGraph agent with observe/reason/act cycle, rolling memory, command dedup, JSONL decision logging, and role-specific red/blue prompts.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Base agent with LangGraph reasoning loop + memory | 3eada3f | agents/base_agent.py, agents/requirements.txt |
| 2 | Red/blue agent configs | 6ad0be3 | agents/red_agent/agent.py, agents/blue_agent/agent.py |

## What Was Built

### Base Agent (agents/base_agent.py)
- LangGraph StateGraph with 4 nodes: observe, reason, act, check_done
- Rolling short-term memory: last 5 observations kept in sliding window
- Long-term memory: key findings persisted as JSON list (notable command results)
- Command deduplication: executed_commands tracked; duplicates modified or skipped
- Context window management: total prompt capped at 8192 chars (~2048 tokens)
- JSONL decision logging at /app/data/decisions.jsonl with timestamp, reasoning, exit code, blocked status
- 60-second timeout on LLM inference calls
- JSON response parsing with regex fallback for freeform LLM output
- Configurable via ORCHESTRATOR_URL, INFERENCE_URL environment variables

### Red Agent (agents/red_agent/agent.py)
- Kill chain prompt: recon, exploit, persist
- Imports shared base_agent.run_agent()
- Configurable MAX_TURNS via environment

### Blue Agent (agents/blue_agent/agent.py)
- Defense prompt: assess posture, harden, monitor
- Same architecture as red agent with defensive system prompt

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| List instead of set for executed_commands | JSON serialisation compatibility with LangGraph state |
| Regex fallback for LLM parsing | Gemma 4 may not always produce clean JSON; graceful degradation |
| sys.path.insert for imports | Agent containers COPY from subdirectories; needs parent path for base_agent |
| 8192 char prompt cap | 4 chars/token heuristic keeps within 2048 token budget for KoboldCpp |

## Deviations from Plan

None -- plan executed exactly as written.

## Files Created

- `agents/base_agent.py` - Core LangGraph agent loop
- `agents/requirements.txt` - Python dependencies (langgraph, langchain-core, requests, pydantic)
- `agents/red_agent/agent.py` - Red team entry point
- `agents/blue_agent/agent.py` - Blue team entry point

## Next Steps

- Update agent Dockerfiles to install from requirements.txt and run agent.py instead of main.py
- Deploy to server with K80 GPU and test end-to-end with KoboldCpp inference
- Validate Gemma 4 JSON output quality with actual game prompts
