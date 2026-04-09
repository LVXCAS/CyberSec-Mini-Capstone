"""Blue team response skills — kill processes, remove unauthorized users."""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger("skills.blue.respond")

# Users that must never be removed — critical system accounts.
PROTECTED_USERS = frozenset({"root", "ubuntu", "www-data"})


def _execute_on_orchestrator(
    command: str,
    orchestrator_url: str,
    agent_role: str,
    reasoning: str,
    timeout: int = 30,
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


def kill_process(
    pid: int,
    orchestrator_url: str,
    agent_role: str = "blue",
) -> dict[str, Any]:
    """Kill a process by PID using SIGKILL.

    Returns ``{"success": bool, "killed_pid": int}``.
    """
    command = f"kill -9 {pid}"
    data = _execute_on_orchestrator(
        command=command,
        orchestrator_url=orchestrator_url,
        agent_role=agent_role,
        reasoning=f"kill_process pid={pid}",
    )

    success = bool(data.get("allowed") and data.get("result") is not None)
    return {"success": success, "killed_pid": pid}


def remove_user(
    username: str,
    orchestrator_url: str,
    agent_role: str = "blue",
) -> dict[str, Any]:
    """Remove a user account and their home directory.

    Refuses to remove protected system accounts (root, ubuntu, www-data).
    Returns ``{"success": bool, "removed_user": str}``.
    """
    if username in PROTECTED_USERS:
        logger.warning("Refused to remove protected user: %s", username)
        return {
            "success": False,
            "removed_user": username,
            "error": f"'{username}' is a protected user and cannot be removed",
        }

    command = f'userdel -r {username} 2>/dev/null; echo "done"'
    data = _execute_on_orchestrator(
        command=command,
        orchestrator_url=orchestrator_url,
        agent_role=agent_role,
        reasoning=f"remove_user username={username}",
    )

    success = bool(data.get("allowed") and data.get("result") is not None)
    return {"success": success, "removed_user": username}
