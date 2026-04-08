"""Blocklist-based command safety filter for the orchestrator."""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel


class FilterResult(BaseModel):
    allowed: bool
    command: str
    reason: Optional[str] = None
    sanitized_command: Optional[str] = None


# Dangerous command patterns (regex)
BLOCKLIST_PATTERNS: list[tuple[str, str]] = [
    (r"rm\s+-rf\s+/", "Recursive delete of root filesystem"),
    (r"mkfs\b", "Filesystem format command"),
    (r"dd\s+if=", "Raw disk write command"),
    (r"\bshutdown\b", "System shutdown command"),
    (r"\breboot\b", "System reboot command"),
    (r"\bhalt\b", "System halt command"),
    (r"\bpoweroff\b", "System poweroff command"),
    (r":\(\)\{", "Fork bomb pattern"),
    (r">\s*/dev/sd", "Direct write to block device"),
    (r"chmod\s+777\s+/", "Dangerous permission change on root"),
    (r"wget\s+.*\|\s*sh", "Remote code execution via wget pipe"),
    (r"curl\s+.*\|\s*sh", "Remote code execution via curl pipe"),
    (r"wget\s+.*\|\s*bash", "Remote code execution via wget pipe"),
    (r"curl\s+.*\|\s*bash", "Remote code execution via curl pipe"),
]

# Role-based restrictions: {role: [(pattern, reason), ...]}
ROLE_RESTRICTIONS: dict[str, list[tuple[str, str]]] = {
    "blue": [
        (r"\bnmap\b", "Blue agent cannot run offensive scanning tools"),
        (r"\bmetasploit\b", "Blue agent cannot run exploitation tools"),
        (r"\bhydra\b", "Blue agent cannot run brute-force tools"),
    ],
    "red": [
        (r"\bauditd\b", "Red agent cannot run audit/defense tools"),
        (r"\biptables\b", "Red agent cannot modify firewall rules"),
        (r"\bufw\b", "Red agent cannot modify firewall rules"),
        (r"\bfail2ban\b", "Red agent cannot configure intrusion prevention"),
    ],
}


def validate_command(command: str, agent_role: str) -> FilterResult:
    """Validate a command against the blocklist and role restrictions.

    Args:
        command: The shell command to validate.
        agent_role: The role of the agent (e.g., "red", "blue").

    Returns:
        FilterResult indicating whether the command is allowed.
    """
    # Check global blocklist
    for pattern, reason in BLOCKLIST_PATTERNS:
        if re.search(pattern, command):
            return FilterResult(
                allowed=False,
                command=command,
                reason=f"BLOCKED: {reason} (matched: {pattern})",
            )

    # Check role-based restrictions
    # Normalize role: "red-agent" -> "red", "blue-agent" -> "blue"
    normalized_role = agent_role.split("-")[0].lower()
    role_rules = ROLE_RESTRICTIONS.get(normalized_role, [])
    for pattern, reason in role_rules:
        if re.search(pattern, command):
            return FilterResult(
                allowed=False,
                command=command,
                reason=f"ROLE BLOCKED ({agent_role}): {reason}",
            )

    return FilterResult(
        allowed=True,
        command=command,
        sanitized_command=command,
    )
