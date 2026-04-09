"""
Base autonomous agent using LangGraph StateGraph.

Implements observe -> reason -> tool_dispatcher -> check_done loop with:
- Skill-based dispatch (LLM picks skill name + parameters)
- Rolling short-term memory (last 5 observations)
- Long-term memory (key findings as JSON)
- Skill call deduplication (name + sorted params)
- JSONL decision logging
- Turn limits
- Context window management (< 2048 tokens ~ 8192 chars)
- Parse failure recovery (up to 3 retries before default skill)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

import requests
from langgraph.graph import END, StateGraph

from skills.registry import SKILL_REGISTRY, execute_skill

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
MAX_PARSE_FAILURES = 3

# Default fallback skills per role when parse failures exhaust retries
_DEFAULT_SKILLS: dict[str, dict] = {
    "red": {"name": "port_scan", "parameters": {"target": "10.0.0.5"}},
    "blue": {"name": "scan_processes", "parameters": {}},
}

# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------


class AgentState(TypedDict):
    agent_role: str
    system_prompt: str
    turn_number: int
    max_turns: int
    observations: list[str]
    executed_skills: list[str]  # hashes of (name + sorted params) for dedup
    findings: list[dict]
    messages: list[dict]
    done: bool
    last_result: dict
    available_skills: list[dict]  # skill metadata for prompt
    game_phase: str  # "setup" or "battle"
    parse_failures: int  # consecutive parse failure count


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _truncate(text: str, max_len: int = 200) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _skill_hash(name: str, params: dict) -> str:
    """Create a deduplication hash from skill name + sorted parameters."""
    key = json.dumps({"name": name, "params": params}, sort_keys=True)
    return hashlib.md5(key.encode()).hexdigest()


def _parse_skill_call(text: str) -> dict | None:
    """Parse a skill call from LLM output.

    Returns dict with 'name', 'parameters', and optionally 'reasoning',
    or None if parsing fails completely.

    Layers:
    1. Direct JSON parse for {"name": ..., "parameters": ...}
    2. Regex to extract JSON block from mixed text
    3. Regex for individual fields from partial JSON
    4. None (caller handles re-reasoning)
    """
    stripped = text.strip()

    # Layer 1: Direct JSON parse
    try:
        data = json.loads(stripped)
        if isinstance(data, dict) and "name" in data:
            return {
                "name": data["name"],
                "parameters": data.get("parameters", {}),
                "reasoning": data.get("reasoning", ""),
            }
    except (json.JSONDecodeError, ValueError):
        pass

    # Layer 2: Regex to find JSON block containing "name"
    json_match = re.search(r'\{[^{}]*"name"[^{}]*\}', text)
    if json_match:
        try:
            data = json.loads(json_match.group())
            if "name" in data:
                return {
                    "name": data["name"],
                    "parameters": data.get("parameters", {}),
                    "reasoning": data.get("reasoning", ""),
                }
        except (json.JSONDecodeError, ValueError):
            pass

    # Layer 3: Extract name and parameters separately
    name_match = re.search(r'"name"\s*:\s*"(\w+)"', text)
    params_match = re.search(r'"parameters"\s*:\s*(\{[^}]*\})', text)
    if name_match:
        params = {}
        if params_match:
            try:
                params = json.loads(params_match.group(1))
            except (json.JSONDecodeError, ValueError):
                pass
        reasoning_match = re.search(r'"reasoning"\s*:\s*"([^"]*)"', text)
        return {
            "name": name_match.group(1),
            "parameters": params,
            "reasoning": reasoning_match.group(1) if reasoning_match else "",
        }

    # Layer 4: Complete failure
    return None


def _build_prompt(state: AgentState) -> list[dict]:
    """Build LLM messages list with skill-aware prompt, capped at MAX_PROMPT_CHARS."""
    system = state["system_prompt"]

    # Format available skills as compact JSON list for the system message
    skills_json = json.dumps(state["available_skills"], indent=1)

    observations_block = "\n".join(
        f"[Turn {i+1}] {obs}"
        for i, obs in enumerate(state["observations"][-MAX_OBSERVATION_WINDOW:])
    )

    findings_block = (
        json.dumps(state["findings"][-10:], indent=1)
        if state["findings"]
        else "None yet."
    )

    executed_block = (
        ", ".join(state["executed_skills"][-20:])
        if state["executed_skills"]
        else "None yet."
    )

    turn = state["turn_number"]
    max_turns = state["max_turns"]
    remaining = max_turns - turn
    phase = state.get("game_phase", "battle")
    role = state["agent_role"]

    # Adaptive instructions based on role and phase
    phase_instruction = ""
    if role == "red":
        if remaining <= max_turns * 0.3:
            phase_instruction = (
                "WARNING: Running low on turns. Escalate aggression. "
                "Try multiple attack vectors simultaneously."
            )
    elif role == "blue":
        if phase == "setup":
            phase_instruction = (
                "PHASE: Setup. Focus on hardening: apply firewall rules, "
                "harden SSH, check for SUID binaries, configure monitoring."
            )
        else:
            phase_instruction = (
                "PHASE: Battle. Balance detection and response. "
                "Poll for intrusion signs, then act on findings."
            )

    user_content = (
        f"## Current Situation\n"
        f"Turn: {turn}/{max_turns}\n"
        f"Remaining turns: {remaining}\n"
        f"Game phase: {phase}\n\n"
        f"{phase_instruction}\n\n"
        f"## Available Skills\n{skills_json}\n\n"
        f"## Recent Observations (short-term memory)\n{observations_block}\n\n"
        f"## Key Findings (long-term memory)\n{findings_block}\n\n"
        f"## Skills Already Used (hashes — do NOT repeat identical calls)\n{executed_block}\n\n"
        f"## Your Task\n"
        f"Choose your next action. Respond ONLY with JSON:\n"
        f'  {{"name": "skill_name", "parameters": {{"key": "value"}}, "reasoning": "why this skill"}}\n'
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


def _log_decision(
    agent_role: str,
    turn: int,
    skill_name: str,
    reasoning: str,
    result: dict,
    was_blocked: bool,
) -> None:
    """Append one JSONL line to the decisions log."""
    DECISIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_role": agent_role,
        "turn": turn,
        "skill": skill_name,
        "reasoning": reasoning,
        "result_preview": _truncate(str(result), 200),
        "was_blocked": was_blocked,
    }
    with open(DECISIONS_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------


def observe_node(state: AgentState) -> dict:
    """Query orchestrator for last action result or run initial observation."""
    role = state["agent_role"]
    observations = list(state["observations"])

    if state["turn_number"] == 0:
        initial = f"Agent {role} starting. No previous observations."
        observations.append(initial)
    else:
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

    observations = observations[-MAX_OBSERVATION_WINDOW:]
    return {"observations": observations}


def reason_node(state: AgentState) -> dict:
    """Call LLM to decide next skill call."""
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
        # On LLM failure, produce a fallback skill call
        role = state["agent_role"]
        fallback = _DEFAULT_SKILLS.get(role, _DEFAULT_SKILLS["blue"])
        llm_text = json.dumps({**fallback, "reasoning": f"LLM call failed ({e}); fallback"})

    return {"messages": [{"role": "assistant", "content": llm_text}]}


def tool_dispatcher_node(state: AgentState) -> dict:
    """Parse LLM output and dispatch to the appropriate skill."""
    role = state["agent_role"]
    turn = state["turn_number"]

    last_msg = state["messages"][-1] if state["messages"] else {}
    llm_text = last_msg.get("content", "")

    parsed = _parse_skill_call(llm_text)
    observations = list(state["observations"])
    parse_failures = state.get("parse_failures", 0)

    # --- Parse failure handling ---
    if parsed is None:
        parse_failures += 1
        if parse_failures >= MAX_PARSE_FAILURES:
            # Force default skill after too many failures
            parsed = _DEFAULT_SKILLS.get(role, _DEFAULT_SKILLS["blue"]).copy()
            parsed["reasoning"] = "Forced default after parse failures"
            parse_failures = 0
        else:
            skill_names = [s["name"] for s in state.get("available_skills", [])]
            observations.append(
                f"Failed to parse skill call. Please respond with ONLY JSON: "
                f'{{"name": "skill_name", "parameters": {{...}}, "reasoning": "..."}}. '
                f"Available skills: {', '.join(skill_names)}"
            )
            observations = observations[-MAX_OBSERVATION_WINDOW:]
            return {
                "observations": observations,
                "parse_failures": parse_failures,
                # Do NOT increment turn_number
            }

    skill_name = parsed["name"]
    params = parsed.get("parameters", {})
    reasoning = parsed.get("reasoning", "")

    # --- Unknown skill handling ---
    if skill_name not in SKILL_REGISTRY:
        parse_failures += 1
        skill_names = [s["name"] for s in state.get("available_skills", [])]
        if parse_failures >= MAX_PARSE_FAILURES:
            parsed = _DEFAULT_SKILLS.get(role, _DEFAULT_SKILLS["blue"]).copy()
            parsed["reasoning"] = "Forced default after unknown skill attempts"
            skill_name = parsed["name"]
            params = parsed.get("parameters", {})
            reasoning = parsed.get("reasoning", "")
            parse_failures = 0
        else:
            observations.append(
                f"Unknown skill '{skill_name}'. Available: {', '.join(skill_names)}"
            )
            observations = observations[-MAX_OBSERVATION_WINDOW:]
            return {
                "observations": observations,
                "parse_failures": parse_failures,
            }

    # --- Deduplication ---
    call_hash = _skill_hash(skill_name, params)
    executed = list(state.get("executed_skills", []))

    # --- Execute skill ---
    result = execute_skill(skill_name, params, ORCHESTRATOR_URL)
    was_blocked = not result.get("success", True)

    _log_decision(role, turn, skill_name, reasoning, result, was_blocked)
    executed.append(call_hash)

    # Build observation from result
    result_preview = _truncate(str(result), 150)
    result_obs = f"Skill: {skill_name} | Result: {result_preview}"
    observations.append(result_obs)
    observations = observations[-MAX_OBSERVATION_WINDOW:]

    # Update findings if notable
    findings = list(state["findings"])
    if result.get("success", False):
        findings.append({
            "turn": turn,
            "skill": skill_name,
            "summary": _truncate(str(result), 100),
        })

    return {
        "turn_number": turn + 1,
        "executed_skills": executed,
        "findings": findings,
        "observations": observations,
        "last_result": result,
        "parse_failures": 0,  # Reset on successful dispatch
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


def after_dispatcher(state: AgentState) -> str:
    """Edge function after tool_dispatcher: check if parse failed (no turn increment)."""
    # If turn wasn't incremented (parse failure), go back to reason
    # We detect this by checking parse_failures > 0
    if state.get("parse_failures", 0) > 0:
        return "reason"
    return "check_done"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_agent_graph() -> Any:
    """Build and compile the agent StateGraph."""
    graph = StateGraph(AgentState)

    graph.add_node("observe", observe_node)
    graph.add_node("reason", reason_node)
    graph.add_node("tool_dispatcher", tool_dispatcher_node)
    graph.add_node("check_done", check_done_node)

    graph.set_entry_point("observe")
    graph.add_edge("observe", "reason")
    graph.add_edge("reason", "tool_dispatcher")
    graph.add_conditional_edges(
        "tool_dispatcher",
        after_dispatcher,
        {"reason": "reason", "check_done": "check_done"},
    )
    graph.add_conditional_edges(
        "check_done",
        should_continue,
        {"observe": "observe", "end": END},
    )

    return graph.compile()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_agent(
    role: str,
    system_prompt: str,
    max_turns: int = 15,
    available_skills: list[dict] | None = None,
    game_phase: str = "battle",
) -> dict:
    """Run the autonomous agent loop.

    Args:
        role: Agent role identifier (e.g. "red", "blue").
        system_prompt: Role-specific system prompt for the LLM.
        max_turns: Maximum number of reasoning turns.
        available_skills: Skill metadata list for the prompt.
        game_phase: Current game phase ("setup" or "battle").

    Returns:
        Final agent state dict with findings and executed skills.
    """
    agent = build_agent_graph()

    initial_state: AgentState = {
        "agent_role": role,
        "system_prompt": system_prompt,
        "turn_number": 0,
        "max_turns": max_turns,
        "observations": [],
        "executed_skills": [],
        "findings": [],
        "messages": [],
        "done": False,
        "last_result": {},
        "available_skills": available_skills or [],
        "game_phase": game_phase,
        "parse_failures": 0,
    }

    final_state = agent.invoke(initial_state)
    return final_state
