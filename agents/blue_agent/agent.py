"""
Blue team autonomous agent.

Wraps the base agent with a blue-team system prompt focused on
hardening, monitoring, and defending the server.
"""

import os
import sys

# Allow importing base_agent from parent directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from base_agent import run_agent  # noqa: E402

BLUE_SYSTEM_PROMPT = (
    "You are an autonomous blue team defender. Your mission is to harden, "
    "monitor, and defend the server. You see a remote server you are responsible "
    "for protecting. Respond ONLY with JSON: "
    '{"tool": "execute", "args": {"cmd": "command_here"}, "reasoning": "why this command"}. '
    "Start by assessing the current security posture. Apply hardening measures. "
    "Set up monitoring."
)

MAX_TURNS = int(os.getenv("MAX_TURNS", "15"))


def main() -> None:
    """Entry point for the blue agent container."""
    print(f"[BLUE AGENT] Starting autonomous loop — max {MAX_TURNS} turns")
    result = run_agent("blue", BLUE_SYSTEM_PROMPT, max_turns=MAX_TURNS)
    print(f"[BLUE AGENT] Complete — {result.get('turn_number', '?')} turns executed")
    print(f"[BLUE AGENT] Findings: {len(result.get('findings', []))}")
    print(f"[BLUE AGENT] Commands: {len(result.get('executed_commands', []))}")


if __name__ == "__main__":
    main()
