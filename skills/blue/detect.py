"""Blue team detection skills — process scanning, auth log analysis, user enumeration."""

from __future__ import annotations

import logging
import re
from typing import Any

import requests

logger = logging.getLogger("skills.blue.detect")

# Filter out the blue agent's own activity from suspicious results.
BLUE_AGENT_IP = "blue-agent"

# System processes that are expected and should not be flagged as suspicious.
SYSTEM_USERS = frozenset({
    "root", "daemon", "bin", "sys", "sync", "games", "man", "lp", "mail",
    "news", "uucp", "proxy", "www-data", "backup", "list", "irc", "gnats",
    "nobody", "systemd-network", "systemd-resolve", "systemd-timesync",
    "messagebus", "syslog", "sshd", "ntp", "_apt",
})

SYSTEM_COMMANDS = frozenset({
    "/sbin/init", "/lib/systemd/systemd", "/usr/sbin/sshd",
    "/usr/sbin/cron", "/usr/sbin/rsyslogd",
})


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


def _is_system_process(user: str, command: str) -> bool:
    """Return True if the process is a known system process."""
    if user in SYSTEM_USERS and any(command.startswith(sc) for sc in SYSTEM_COMMANDS):
        return True
    # sshd owned by root is expected
    if user == "root" and "sshd" in command:
        return True
    return False


def scan_processes(
    orchestrator_url: str,
    agent_role: str = "blue",
) -> dict[str, Any]:
    """Scan running processes and identify suspicious ones.

    Returns ``{"processes": list[dict], "suspicious": list[dict]}``.
    Suspicious = processes owned by non-root/non-system users, excluding
    the blue agent's own activity.
    """
    command = "ps aux --no-headers"
    data = _execute_on_orchestrator(
        command=command,
        orchestrator_url=orchestrator_url,
        agent_role=agent_role,
        reasoning="scan_processes detect anomalous activity",
    )

    if not data.get("allowed") or data.get("result") is None:
        return {"processes": [], "suspicious": []}

    stdout = data["result"].get("stdout", "")
    processes: list[dict[str, Any]] = []
    suspicious: list[dict[str, Any]] = []

    for line in stdout.strip().splitlines():
        parts = line.split(None, 10)
        if len(parts) < 11:
            continue
        user = parts[0]
        pid = int(parts[1])
        cmd = parts[10]

        entry = {"user": user, "pid": pid, "command": cmd}
        processes.append(entry)

        # Skip blue agent's own activity
        if BLUE_AGENT_IP in cmd:
            continue

        if not _is_system_process(user, cmd) and user not in SYSTEM_USERS:
            suspicious.append(entry)

    return {"processes": processes, "suspicious": suspicious}


def tail_auth_log(
    orchestrator_url: str,
    agent_role: str = "blue",
    lines: int = 50,
) -> dict[str, Any]:
    """Tail the auth log for login attempts, new users, and sudo events.

    Returns parsed summary of authentication activity.
    """
    command = (
        f"tail -n {lines} /var/log/auth.log 2>/dev/null"
        f" || tail -n {lines} /var/log/secure 2>/dev/null"
    )
    data = _execute_on_orchestrator(
        command=command,
        orchestrator_url=orchestrator_url,
        agent_role=agent_role,
        reasoning="tail_auth_log check for intrusion indicators",
        timeout=15,
    )

    empty_result: dict[str, Any] = {
        "raw_lines": 0,
        "failed_logins": 0,
        "successful_logins": [],
        "new_users": [],
        "sudo_events": [],
    }

    if not data.get("allowed") or data.get("result") is None:
        return empty_result

    stdout = data["result"].get("stdout", "")
    log_lines = stdout.strip().splitlines()

    failed_logins = 0
    successful_logins: list[dict[str, str]] = []
    new_users: list[str] = []
    sudo_events: list[str] = []

    failed_re = re.compile(r"Failed password for (\S+) from (\S+)")
    accepted_re = re.compile(r"Accepted \S+ for (\S+) from (\S+)")
    useradd_re = re.compile(r"useradd.*?name=(\S+)")
    sudo_re = re.compile(r"sudo:\s+(\S+).*COMMAND=(.*)")

    for line in log_lines:
        # Filter out blue agent's own activity
        if BLUE_AGENT_IP in line:
            continue

        match_failed = failed_re.search(line)
        if match_failed:
            failed_logins += 1
            continue

        match_accepted = accepted_re.search(line)
        if match_accepted:
            successful_logins.append({
                "user": match_accepted.group(1),
                "from_ip": match_accepted.group(2),
            })
            continue

        match_useradd = useradd_re.search(line)
        if match_useradd:
            new_users.append(match_useradd.group(1))
            continue

        match_sudo = sudo_re.search(line)
        if match_sudo:
            sudo_events.append(f"{match_sudo.group(1)}: {match_sudo.group(2)}")

    return {
        "raw_lines": len(log_lines),
        "failed_logins": failed_logins,
        "successful_logins": successful_logins,
        "new_users": new_users,
        "sudo_events": sudo_events,
    }


def list_users(
    orchestrator_url: str,
    agent_role: str = "blue",
) -> dict[str, Any]:
    """List human users (UID >= 1000) from /etc/passwd.

    Returns ``{"users": list[dict], "count": int}``.
    """
    command = "awk -F: '$3 >= 1000 && $3 < 65534 {print $1\":\"$3\":\"$7}' /etc/passwd"
    data = _execute_on_orchestrator(
        command=command,
        orchestrator_url=orchestrator_url,
        agent_role=agent_role,
        reasoning="list_users enumerate human accounts",
    )

    if not data.get("allowed") or data.get("result") is None:
        return {"users": [], "count": 0}

    stdout = data["result"].get("stdout", "")
    users: list[dict[str, Any]] = []

    for line in stdout.strip().splitlines():
        parts = line.split(":")
        if len(parts) >= 3:
            users.append({
                "username": parts[0],
                "uid": int(parts[1]),
                "shell": parts[2],
            })

    return {"users": users, "count": len(users)}
