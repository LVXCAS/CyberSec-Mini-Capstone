"""Red team reconnaissance skills — port scanning and service enumeration."""

from __future__ import annotations

import logging
import re
from typing import Any

import requests

logger = logging.getLogger("skills.red.recon")


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


def port_scan(
    target: str,
    orchestrator_url: str,
    agent_role: str = "red",
) -> dict[str, Any]:
    """Scan ports 1-1000 on the target using nmap TCP connect scan.

    Returns a dict with target, open_ports list, and success flag.
    Each open port entry contains port (int), service (str), version (str).
    """
    command = f"nmap -T4 -sT -sV --open -p 1-1000 {target}"
    data = _execute_on_orchestrator(
        command=command,
        orchestrator_url=orchestrator_url,
        agent_role=agent_role,
        reasoning=f"port_scan target={target}",
        timeout=120,
    )

    if not data.get("allowed") or data.get("result") is None:
        return {
            "success": False,
            "error": data.get("reason", "command not allowed or no result"),
            "target": target,
            "open_ports": [],
        }

    stdout = data["result"].get("stdout", "")
    open_ports: list[dict[str, Any]] = []

    # Parse nmap output: lines like "22/tcp   open  ssh     OpenSSH 8.9"
    pattern = re.compile(r"^(\d+)/tcp\s+open\s+(\S+)\s*(.*)", re.MULTILINE)
    for match in pattern.finditer(stdout):
        open_ports.append({
            "port": int(match.group(1)),
            "service": match.group(2),
            "version": match.group(3).strip(),
        })

    return {"success": True, "target": target, "open_ports": open_ports}


def service_enum(
    target: str,
    port: int,
    orchestrator_url: str,
    agent_role: str = "red",
) -> dict[str, Any]:
    """Run detailed service enumeration on a specific port using nmap scripts.

    Returns a dict with target, port, and detailed output.
    """
    command = f"nmap -sT -sV -sC -p {port} {target}"
    data = _execute_on_orchestrator(
        command=command,
        orchestrator_url=orchestrator_url,
        agent_role=agent_role,
        reasoning=f"service_enum target={target} port={port}",
        timeout=120,
    )

    if not data.get("allowed") or data.get("result") is None:
        return {
            "success": False,
            "error": data.get("reason", "command not allowed or no result"),
            "target": target,
            "port": port,
            "details": "",
        }

    stdout = data["result"].get("stdout", "")
    return {"success": True, "target": target, "port": port, "details": stdout}
