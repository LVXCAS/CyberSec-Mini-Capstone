"""Skill registry — maps skill names to callable functions and metadata."""

from __future__ import annotations

import logging
from typing import Any, Callable

from skills.red.exploit import ssh_brute, web_sqli_check
from skills.red.persistence import add_backdoor_user, add_ssh_key, install_cron_backdoor
from skills.red.privesc import find_suid
from skills.blue import register_blue_skills
from skills.red.recon import port_scan, service_enum

logger = logging.getLogger("skills.registry")

SKILL_REGISTRY: dict[str, dict[str, Any]] = {}


def _register(
    name: str,
    description: str,
    parameters: dict[str, str],
    function: Callable[..., dict[str, Any]],
    role: str,
) -> None:
    """Register a skill in the global registry."""
    SKILL_REGISTRY[name] = {
        "name": name,
        "description": description,
        "parameters": parameters,
        "function": function,
        "role": role,
    }


def get_skills_for_role(role: str) -> list[dict[str, Any]]:
    """Return skill metadata (name, description, parameters) for a given role."""
    return [
        {"name": s["name"], "description": s["description"], "parameters": s["parameters"]}
        for s in SKILL_REGISTRY.values()
        if s["role"] == role
    ]


def execute_skill(
    name: str,
    params: dict[str, Any],
    orchestrator_url: str,
) -> dict[str, Any]:
    """Look up a skill by name and execute it with the given parameters."""
    skill = SKILL_REGISTRY.get(name)
    if skill is None:
        return {"success": False, "error": f"unknown skill: {name}"}

    fn = skill["function"]
    try:
        return fn(orchestrator_url=orchestrator_url, **params)
    except TypeError as exc:
        return {"success": False, "error": f"invalid parameters: {exc}"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Skill %s failed", name)
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Register red team skills — recon
# ---------------------------------------------------------------------------

_register(
    name="port_scan",
    description="Scan TCP ports 1-1000 on a target host and enumerate services.",
    parameters={"target": "IP address or hostname to scan"},
    function=port_scan,
    role="red",
)

_register(
    name="service_enum",
    description="Run detailed service enumeration (nmap scripts) on a specific port.",
    parameters={
        "target": "IP address or hostname",
        "port": "Port number to enumerate",
    },
    function=service_enum,
    role="red",
)

# ---------------------------------------------------------------------------
# Register red team skills — exploit
# ---------------------------------------------------------------------------

_register(
    name="ssh_brute",
    description="Brute force SSH credentials using hydra with a wordlist.",
    parameters={
        "target": "IP address or hostname with SSH",
        "username": "Username to brute force",
        "wordlist": "(optional) Path to password wordlist",
    },
    function=ssh_brute,
    role="red",
)

_register(
    name="web_sqli_check",
    description="Check a URL for basic SQL injection vulnerability.",
    parameters={"url": "Full URL of the login endpoint to test"},
    function=web_sqli_check,
    role="red",
)

# ---------------------------------------------------------------------------
# Register red team skills — privesc
# ---------------------------------------------------------------------------

_register(
    name="find_suid",
    description="Find SUID binaries on the target that may be exploitable for privilege escalation.",
    parameters={},
    function=find_suid,
    role="red",
)

# ---------------------------------------------------------------------------
# Register red team skills — persistence
# ---------------------------------------------------------------------------

_register(
    name="add_backdoor_user",
    description="Create a backdoor user account with bash shell access.",
    parameters={
        "username": "Username for the backdoor account",
        "password": "Password for the backdoor account",
    },
    function=add_backdoor_user,
    role="red",
)

_register(
    name="install_cron_backdoor",
    description="Install a cron-based reverse shell that fires every 5 minutes.",
    parameters={
        "callback_ip": "IP address to connect back to",
        "port": "Port number for the reverse shell",
    },
    function=install_cron_backdoor,
    role="red",
)

_register(
    name="add_ssh_key",
    description="Add an SSH public key to a target user's authorized_keys file.",
    parameters={
        "target_user": "Username whose authorized_keys to modify",
        "pubkey": "SSH public key string to add",
    },
    function=add_ssh_key,
    role="red",
)

# ---------------------------------------------------------------------------
# Register blue team skills
# ---------------------------------------------------------------------------

register_blue_skills(SKILL_REGISTRY)
