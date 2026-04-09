"""
Red team autonomous agent.

Wraps the base agent with a red-team system prompt focused on
reconnaissance, exploitation, privilege escalation, and persistence.
Skills are advertised in the prompt so the LLM picks from the registry.
"""

import json
import os
import sys

# Allow importing base_agent from parent directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from base_agent import run_agent  # noqa: E402
from skills.registry import get_skills_for_role  # noqa: E402

MAX_TURNS = int(os.getenv("MAX_TURNS", "15"))

RED_SYSTEM_PROMPT = (
    "You are an autonomous red team operator.\n\n"
    "MISSION: Complete the kill chain — reconnaissance -> exploitation -> "
    "privilege escalation -> persistence.\n\n"
    "STRATEGY:\n"
    "- Be methodical: start with recon to map the attack surface.\n"
    "- Progress through the kill chain in order.\n"
    "- If running low on turns (below 30% remaining), escalate aggression "
    "and try multiple attack vectors.\n"
    "- Adapt based on observations — if one approach fails, pivot.\n\n"
    "IMPORTANT: Respond ONLY with a JSON skill call. No explanations outside JSON.\n"
    'Format: {"name": "skill_name", "parameters": {"key": "value"}, "reasoning": "why"}\n'
)


def main() -> None:
    """Entry point for the red agent container."""
    skills = get_skills_for_role("red")
    print(f"[RED AGENT] Starting autonomous loop — max {MAX_TURNS} turns")
    print(f"[RED AGENT] Available skills: {json.dumps([s['name'] for s in skills])}")

    result = run_agent(
        role="red",
        system_prompt=RED_SYSTEM_PROMPT,
        max_turns=MAX_TURNS,
        available_skills=skills,
        game_phase="battle",
    )

    print(f"[RED AGENT] Complete — {result.get('turn_number', '?')} turns executed")
    print(f"[RED AGENT] Findings: {len(result.get('findings', []))}")
    print(f"[RED AGENT] Skills used: {len(result.get('executed_skills', []))}")


if __name__ == "__main__":
    main()
