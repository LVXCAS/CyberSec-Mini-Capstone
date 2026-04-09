"""Blue team hardening skills — firewall rules, SSH config, SUID remediation."""

from __future__ import annotations

import logging
import shlex
from typing import Any

import requests

logger = logging.getLogger("skills.blue.harden")


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


def block_ip(
    ip: str,
    orchestrator_url: str,
    agent_role: str = "blue",
) -> dict[str, Any]:
    """Block an IP address using ufw firewall rule.

    Returns ``{"success": bool, "blocked_ip": str}``.
    """
    safe_ip = shlex.quote(ip)
    command = f"ufw deny from {safe_ip} to any"
    data = _execute_on_orchestrator(
        command=command,
        orchestrator_url=orchestrator_url,
        agent_role=agent_role,
        reasoning=f"block_ip ip={ip}",
    )

    success = bool(data.get("allowed") and data.get("result") is not None)
    return {"success": success, "blocked_ip": ip}


def harden_ssh(
    orchestrator_url: str,
    agent_role: str = "blue",
) -> dict[str, Any]:
    """Harden SSH configuration — disable root login and password auth.

    Returns ``{"success": bool, "changes": list[str]}``.
    """
    command = (
        "sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config"
        " && sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config"
        " && systemctl restart sshd"
    )
    data = _execute_on_orchestrator(
        command=command,
        orchestrator_url=orchestrator_url,
        agent_role=agent_role,
        reasoning="harden_ssh disable root login and password auth",
        timeout=30,
    )

    success = bool(data.get("allowed") and data.get("result") is not None)
    return {
        "success": success,
        "changes": ["PermitRootLogin no", "PasswordAuthentication no"],
    }


def fix_suid(
    binary_path: str,
    orchestrator_url: str,
    agent_role: str = "blue",
) -> dict[str, Any]:
    """Remove SUID bit from a binary.

    Returns ``{"success": bool, "binary": str}``.
    """
    safe_path = shlex.quote(binary_path)
    command = f"chmod u-s {safe_path}"
    data = _execute_on_orchestrator(
        command=command,
        orchestrator_url=orchestrator_url,
        agent_role=agent_role,
        reasoning=f"fix_suid binary={binary_path}",
    )

    success = bool(data.get("allowed") and data.get("result") is not None)
    return {"success": success, "binary": binary_path}
