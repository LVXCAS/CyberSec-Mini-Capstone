"""
Blue team autonomous agent.

Wraps the base agent with a blue-team system prompt focused on
hardening, monitoring, detection, and incident response.
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

BLUE_SYSTEM_PROMPT = (
    "You are an autonomous blue team defender.\n\n"
    "MISSION: Protect the server. Harden it during setup, then detect and "
    "respond to intrusions during battle.\n\n"
    "STRATEGY:\n"
    "- Setup phase: Focus on hardening — apply firewall rules, harden SSH, "
    "check for SUID binaries, configure monitoring.\n"
    "- Battle phase: Balance detection and response. Poll for intrusion signs "
    "(scan_processes, tail_auth_log, list_users), then act on findings "
    "(kill processes, block IPs, remove unauthorized users).\n"
    "- Maintain service uptime — do not take actions that break critical services.\n\n"
    "IMPORTANT: Respond ONLY with a JSON skill call. No explanations outside JSON.\n"
    'Format: {"name": "skill_name", "parameters": {"key": "value"}, "reasoning": "why"}\n'
)


def main() -> None:
    """Entry point for the blue agent container."""
    skills = get_skills_for_role("blue")
    game_phase = os.getenv("GAME_PHASE", "setup")
    print(f"[BLUE AGENT] Starting autonomous loop — max {MAX_TURNS} turns, phase={game_phase}")
    print(f"[BLUE AGENT] Available skills: {json.dumps([s['name'] for s in skills])}")

    result = run_agent(
        role="blue",
        system_prompt=BLUE_SYSTEM_PROMPT,
        max_turns=MAX_TURNS,
        available_skills=skills,
        game_phase=game_phase,
    )

    print(f"[BLUE AGENT] Complete — {result.get('turn_number', '?')} turns executed")
    print(f"[BLUE AGENT] Findings: {len(result.get('findings', []))}")
    print(f"[BLUE AGENT] Skills used: {len(result.get('executed_skills', []))}")


if __name__ == "__main__":
    main()
