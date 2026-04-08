"""
Base autonomous agent using LangGraph StateGraph.

Implements observe -> reason -> act -> check_done loop with:
- Rolling short-term memory (last 5 observations)
- Long-term memory (key findings as JSON)
- Command deduplication
- JSONL decision logging
- Turn limits
- Context window management (< 2048 tokens ~ 8192 chars)
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

import requests
from langgraph.graph import END, StateGraph

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8000")
INFERENCE_URL = os.getenv("INFERENCE_URL", "http://host.docker.internal:5001")
DECISIONS_LOG = Path(os.getenv("DECISIONS_LOG", "/app/data/decisions.jsonl"))
MAX_OBSERVATION_WINDOW = 5
MAX_PROMPT_CHARS = 8192  # ~2048 tokens at 4 chars/token
INFERENCE_TIMEOUT = 60  # seconds
MAX_OUTPUT_TOKENS = 512
LLM_TEMPERATURE = 0.7

# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------


class AgentState(TypedDict):
    agent_role: str
    system_prompt: str
    turn_number: int
    max_turns: int
    observations: list[str]
    executed_commands: list[str]  # list for JSON serialisation; checked as set
    findings: list[dict]
    messages: list[dict]
    done: bool
    last_result: dict


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _truncate(text: str, max_len: int = 200) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _build_prompt(state: AgentState) -> list[dict]:
    """Build LLM messages list, capped at MAX_PROMPT_CHARS."""
    system = state["system_prompt"]

    observations_block = "\n".join(
        f"[Turn {i+1}] {obs}"
        for i, obs in enumerate(state["observations"][-MAX_OBSERVATION_WINDOW:])
    )

    findings_block = json.dumps(state["findings"][-10:], indent=1) if state["findings"] else "None yet."

    executed_block = ", ".join(state["executed_commands"][-20:]) if state["executed_commands"] else "None yet."

    user_content = (
        f"## Current Situation\n"
        f"Turn: {state['turn_number']}/{state['max_turns']}\n"
        f"Remaining turns: {state['max_turns'] - state['turn_number']}\n\n"
        f"## Recent Observations (short-term memory)\n{observations_block}\n\n"
        f"## Key Findings (long-term memory)\n{findings_block}\n\n"
        f"## Commands Already Executed (do NOT repeat)\n{executed_block}\n\n"
        f"## Your Task\n"
        f"Choose your next action. Respond ONLY with JSON:\n"
        f'  {{"tool": "execute", "args": {{"cmd": "your_command"}}, "reasoning": "why"}}\n'
    )

    # Truncate user content if total exceeds budget
    system_len = len(system)
    available = MAX_PROMPT_CHARS - system_len - 100  # 100 char margin
    if len(user_content) > available:
        user_content = user_content[:available]

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


def _parse_llm_response(text: str) -> dict:
    """Parse JSON tool-call from LLM response. Falls back to regex extraction."""
    # Try direct JSON parse
    try:
        data = json.loads(text.strip())
        if "tool" in data and "args" in data:
            return data
    except json.JSONDecodeError:
        pass

    # Try to find JSON block in text
    json_match = re.search(r'\{[^{}]*"tool"[^{}]*"args"[^{}]*\{[^{}]*\}[^{}]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Fallback: extract command from freeform text
    cmd_match = re.search(r'`([^`]+)`', text)
    if cmd_match:
        return {
            "tool": "execute",
            "args": {"cmd": cmd_match.group(1)},
            "reasoning": "Extracted from freeform response",
        }

    # Last resort
    return {
        "tool": "execute",
        "args": {"cmd": "whoami"},
        "reasoning": "Failed to parse LLM response; falling back to safe command",
    }


def _log_decision(
    agent_role: str,
    turn: int,
    command: str,
    reasoning: str,
    exit_code: int,
    stdout: str,
    was_blocked: bool,
) -> None:
    """Append one JSONL line to the decisions log."""
    DECISIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_role": agent_role,
        "turn": turn,
        "command": command,
        "reasoning": reasoning,
        "result_exit_code": exit_code,
        "result_stdout_preview": _truncate(stdout, 200),
        "was_blocked": was_blocked,
    }
    with open(DECISIONS_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------


def observe_node(state: AgentState) -> dict:
    """Query orchestrator for last action result or run initial recon."""
    role = state["agent_role"]
    observations = list(state["observations"])

    if state["turn_number"] == 0:
        # First turn — add initial observation
        initial = f"Agent {role} starting. No previous observations."
        observations.append(initial)
    else:
        # Fetch last decision result from orchestrator
        try:
            resp = requests.get(
                f"{ORCHESTRATOR_URL}/decisions/{role}",
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data:
                    last = data[-1]
                    obs = (
                        f"Command: {last.get('command', 'N/A')} | "
                        f"Exit: {last.get('exit_code', 'N/A')} | "
                        f"Output: {_truncate(last.get('stdout', ''), 150)}"
                    )
                    observations.append(obs)
                else:
                    observations.append("No previous results found.")
            else:
                observations.append(f"Orchestrator returned status {resp.status_code}")
        except requests.RequestException as e:
            observations.append(f"Failed to reach orchestrator: {e}")

    # Rolling window
    observations = observations[-MAX_OBSERVATION_WINDOW:]

    return {"observations": observations}


def reason_node(state: AgentState) -> dict:
    """Call LLM to decide next action."""
    messages = _build_prompt(state)

    try:
        resp = requests.post(
            f"{INFERENCE_URL}/v1/chat/completions",
            json={
                "model": "gemma",
                "messages": messages,
                "max_tokens": MAX_OUTPUT_TOKENS,
                "temperature": LLM_TEMPERATURE,
            },
            timeout=INFERENCE_TIMEOUT,
        )
        resp.raise_for_status()
        llm_text = resp.json()["choices"][0]["message"]["content"]
    except (requests.RequestException, KeyError, IndexError) as e:
        llm_text = json.dumps({
            "tool": "execute",
            "args": {"cmd": "whoami"},
            "reasoning": f"LLM call failed ({e}); safe fallback",
        })

    parsed = _parse_llm_response(llm_text)
    return {"messages": [{"role": "assistant", "content": json.dumps(parsed)}]}


def act_node(state: AgentState) -> dict:
    """Execute the chosen command via orchestrator."""
    role = state["agent_role"]
    turn = state["turn_number"]

    # Get latest reasoning from messages
    last_msg = state["messages"][-1] if state["messages"] else {}
    try:
        action = json.loads(last_msg.get("content", "{}"))
    except json.JSONDecodeError:
        action = {"tool": "execute", "args": {"cmd": "whoami"}, "reasoning": "parse error fallback"}

    command = action.get("args", {}).get("cmd", "whoami")
    reasoning = action.get("reasoning", "")

    # Deduplication check
    executed = list(state["executed_commands"])
    if command in executed:
        # Modify command slightly to avoid exact duplicate
        command = f"{command} 2>&1"
        if command in executed:
            command = f"echo 'skipped duplicate'; {command}"

    # Execute via orchestrator
    exit_code = -1
    stdout = ""
    was_blocked = False

    try:
        resp = requests.post(
            f"{ORCHESTRATOR_URL}/execute",
            json={
                "agent_role": role,
                "command": command,
                "reasoning": reasoning,
                "turn_number": turn,
            },
            timeout=30,
        )
        result = resp.json()
        exit_code = result.get("exit_code", -1)
        stdout = result.get("stdout", "")
        was_blocked = result.get("blocked", False)
    except requests.RequestException as e:
        stdout = f"Orchestrator request failed: {e}"

    # Log decision
    _log_decision(role, turn, command, reasoning, exit_code, stdout, was_blocked)

    # Update executed commands
    executed.append(command)

    # Update findings if notable result
    findings = list(state["findings"])
    if exit_code == 0 and len(stdout) > 10 and not was_blocked:
        findings.append({
            "turn": turn,
            "command": command,
            "summary": _truncate(stdout, 100),
        })

    # Build observation from result
    observations = list(state["observations"])
    result_obs = (
        f"Executed: {command} | Exit: {exit_code} | "
        f"Output: {_truncate(stdout, 150)}"
    )
    observations.append(result_obs)
    observations = observations[-MAX_OBSERVATION_WINDOW:]

    return {
        "turn_number": turn + 1,
        "executed_commands": executed,
        "findings": findings,
        "observations": observations,
        "last_result": {"exit_code": exit_code, "stdout": stdout, "blocked": was_blocked},
    }


def check_done_node(state: AgentState) -> dict:
    """Check if agent should stop."""
    if state["turn_number"] >= state["max_turns"]:
        return {"done": True}
    return {"done": False}


def should_continue(state: AgentState) -> str:
    """Edge function: continue loop or end."""
    if state.get("done", False):
        return "end"
    return "observe"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_agent_graph() -> Any:
    """Build and compile the agent StateGraph."""
    graph = StateGraph(AgentState)

    graph.add_node("observe", observe_node)
    graph.add_node("reason", reason_node)
    graph.add_node("act", act_node)
    graph.add_node("check_done", check_done_node)

    graph.set_entry_point("observe")
    graph.add_edge("observe", "reason")
    graph.add_edge("reason", "act")
    graph.add_edge("act", "check_done")
    graph.add_conditional_edges(
        "check_done",
        should_continue,
        {"observe": "observe", "end": END},
    )

    return graph.compile()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_agent(role: str, system_prompt: str, max_turns: int = 15) -> dict:
    """Run the autonomous agent loop.

    Args:
        role: Agent role identifier (e.g. "red", "blue").
        system_prompt: Role-specific system prompt for the LLM.
        max_turns: Maximum number of reasoning turns.

    Returns:
        Final agent state dict with findings and executed commands.
    """
    agent = build_agent_graph()

    initial_state: AgentState = {
        "agent_role": role,
        "system_prompt": system_prompt,
        "turn_number": 0,
        "max_turns": max_turns,
        "observations": [],
        "executed_commands": [],
        "findings": [],
        "messages": [],
        "done": False,
        "last_result": {},
    }

    final_state = agent.invoke(initial_state)
    return final_state
