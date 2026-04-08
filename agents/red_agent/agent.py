"""
Red team autonomous agent.

Wraps the base agent with a red-team system prompt focused on
reconnaissance, exploitation, and persistent access.
"""

import os
import sys

# Allow importing base_agent from parent directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from base_agent import run_agent  # noqa: E402

RED_SYSTEM_PROMPT = (
    "You are an autonomous red team agent. Your mission is to reconnaissance, "
    "exploit, and gain persistent access to the target server. You see a remote "
    "server you can access. Respond ONLY with JSON: "
    '{"tool": "execute", "args": {"cmd": "command_here"}, "reasoning": "why this command"}. '
    "Start with reconnaissance (network scanning, service enumeration). "
    "Progress methodically through the kill chain."
)

MAX_TURNS = int(os.getenv("MAX_TURNS", "15"))


def main() -> None:
    """Entry point for the red agent container."""
    print(f"[RED AGENT] Starting autonomous loop — max {MAX_TURNS} turns")
    result = run_agent("red", RED_SYSTEM_PROMPT, max_turns=MAX_TURNS)
    print(f"[RED AGENT] Complete — {result.get('turn_number', '?')} turns executed")
    print(f"[RED AGENT] Findings: {len(result.get('findings', []))}")
    print(f"[RED AGENT] Commands: {len(result.get('executed_commands', []))}")


if __name__ == "__main__":
    main()
