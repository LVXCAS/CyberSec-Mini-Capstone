"""Blue team uptime skills — service health checks and restarts."""

from __future__ import annotations

import logging
import shlex
from typing import Any

import requests

logger = logging.getLogger("skills.blue.uptime")


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


def check_service(
    service_name: str,
    orchestrator_url: str,
    agent_role: str = "blue",
) -> dict[str, Any]:
    """Check whether a systemd service is active.

    Returns ``{"service": str, "status": str, "active": bool}``.
    """
    safe_name = shlex.quote(service_name)
    command = f"systemctl is-active {safe_name}"
    data = _execute_on_orchestrator(
        command=command,
        orchestrator_url=orchestrator_url,
        agent_role=agent_role,
        reasoning=f"check_service service={service_name}",
    )

    if not data.get("allowed") or data.get("result") is None:
        return {"service": service_name, "status": "unknown", "active": False}

    stdout = data["result"].get("stdout", "").strip()
    return {
        "service": service_name,
        "status": stdout,
        "active": stdout == "active",
    }


def restart_service(
    service_name: str,
    orchestrator_url: str,
    agent_role: str = "blue",
) -> dict[str, Any]:
    """Restart a systemd service.

    Returns ``{"service": str, "restarted": bool}``.
    """
    safe_name = shlex.quote(service_name)
    command = f"systemctl restart {safe_name}"
    data = _execute_on_orchestrator(
        command=command,
        orchestrator_url=orchestrator_url,
        agent_role=agent_role,
        reasoning=f"restart_service service={service_name}",
    )

    success = bool(data.get("allowed") and data.get("result") is not None)
    return {"service": service_name, "restarted": success}
