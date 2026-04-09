"""Red team privilege escalation skills — SUID binary discovery."""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger("skills.red.privesc")

_SAFE_SUID_BINARIES = frozenset({
    "ping", "sudo", "su", "mount", "umount", "passwd",
    "chsh", "chfn", "newgrp", "gpasswd", "pkexec",
})


def _execute_on_orchestrator(
    command: str,
    orchestrator_url: str,
    agent_role: str,
    reasoning: str,
    timeout: int = 120,
) -> dict[str, Any]:
    """POST a command to the orchestrator /execute endpoint and return parsed JSON."""
    try:
        resp = requests.post(
            f"{orchestrator_url}/execute",
            json={
                "agent_role": agent_role,
                "command": command,
                "reasoning": reasoning,
                "turn_number": 0,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        return {"allowed": False, "reason": "timeout", "result": None}
    except requests.exceptions.ConnectionError as exc:
        return {"allowed": False, "reason": f"connection_error: {exc}", "result": None}
    except Exception as exc:  # noqa: BLE001
        return {"allowed": False, "reason": f"error: {exc}", "result": None}


def find_suid(
    orchestrator_url: str,
    agent_role: str = "red",
) -> dict[str, Any]:
    """Find SUID binaries on the target system that may be exploitable.

    Returns a dict with all SUID binaries found and a filtered list of
    potentially exploitable (non-standard) ones.
    """
    command = "find / -perm -4000 -type f 2>/dev/null"
    data = _execute_on_orchestrator(
        command=command,
        orchestrator_url=orchestrator_url,
        agent_role=agent_role,
        reasoning="find_suid — searching for SUID binaries",
        timeout=60,
    )

    if not data.get("allowed") or data.get("result") is None:
        return {
            "success": False,
            "error": data.get("reason", "command not allowed or no result"),
            "suid_binaries": [],
            "exploitable": [],
        }

    stdout = data["result"].get("stdout", "")
    all_binaries = [line.strip() for line in stdout.splitlines() if line.strip()]

    exploitable = [
        path
        for path in all_binaries
        if path.split("/")[-1] not in _SAFE_SUID_BINARIES
    ]

    return {
        "success": True,
        "suid_binaries": all_binaries,
        "exploitable": exploitable,
    }
