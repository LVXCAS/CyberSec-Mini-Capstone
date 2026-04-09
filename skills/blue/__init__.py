"""Blue team skills — hardening, detection, response, uptime maintenance."""

from __future__ import annotations

from typing import Any

from skills.blue.detect import list_users, scan_processes, tail_auth_log
from skills.blue.harden import block_ip, fix_suid, harden_ssh
from skills.blue.respond import kill_process, remove_user
from skills.blue.uptime import check_service, restart_service


def register_blue_skills(registry: dict[str, Any]) -> None:
    """Register all 10 blue team skills into the provided registry dict.

    Called by the central skills/registry.py (owned by plan 02-01).
    """
    registry["block_ip"] = {
        "name": "block_ip",
        "description": "Block an IP address using ufw firewall rule",
        "parameters": {"ip": "str", "orchestrator_url": "str"},
        "function": block_ip,
        "role": "blue",
    }
    registry["harden_ssh"] = {
        "name": "harden_ssh",
        "description": "Disable root login and password auth in SSH config",
        "parameters": {"orchestrator_url": "str"},
        "function": harden_ssh,
        "role": "blue",
    }
    registry["fix_suid"] = {
        "name": "fix_suid",
        "description": "Remove SUID bit from a binary",
        "parameters": {"binary_path": "str", "orchestrator_url": "str"},
        "function": fix_suid,
        "role": "blue",
    }
    registry["scan_processes"] = {
        "name": "scan_processes",
        "description": "Scan running processes and flag suspicious ones",
        "parameters": {"orchestrator_url": "str"},
        "function": scan_processes,
        "role": "blue",
    }
    registry["tail_auth_log"] = {
        "name": "tail_auth_log",
        "description": "Parse auth log for failed logins, new users, sudo events",
        "parameters": {"orchestrator_url": "str", "lines": "int"},
        "function": tail_auth_log,
        "role": "blue",
    }
    registry["list_users"] = {
        "name": "list_users",
        "description": "List human user accounts (UID >= 1000)",
        "parameters": {"orchestrator_url": "str"},
        "function": list_users,
        "role": "blue",
    }
    registry["kill_process"] = {
        "name": "kill_process",
        "description": "Kill a process by PID",
        "parameters": {"pid": "int", "orchestrator_url": "str"},
        "function": kill_process,
        "role": "blue",
    }
    registry["remove_user"] = {
        "name": "remove_user",
        "description": "Remove a user account (refuses protected users)",
        "parameters": {"username": "str", "orchestrator_url": "str"},
        "function": remove_user,
        "role": "blue",
    }
    registry["check_service"] = {
        "name": "check_service",
        "description": "Check if a systemd service is active",
        "parameters": {"service_name": "str", "orchestrator_url": "str"},
        "function": check_service,
        "role": "blue",
    }
    registry["restart_service"] = {
        "name": "restart_service",
        "description": "Restart a systemd service",
        "parameters": {"service_name": "str", "orchestrator_url": "str"},
        "function": restart_service,
        "role": "blue",
    }
