"""SSH command executor using Paramiko to connect to the battleground."""

from __future__ import annotations

import os
import time
from typing import Optional

import paramiko
from pydantic import BaseModel

MAX_OUTPUT_CHARS = 4096


class CommandResult(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    execution_time_ms: int


def _get_ssh_client() -> paramiko.SSHClient:
    """Create and configure a Paramiko SSH client."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    return client


def execute_command(
    command: str,
    timeout: int = 30,
    hostname: str = "battleground",
    username: str = "admin",
    password: Optional[str] = None,
) -> CommandResult:
    """Execute a command on the battleground via SSH.

    Args:
        command: Shell command to execute.
        timeout: Maximum execution time in seconds.
        hostname: SSH target hostname.
        username: SSH username.
        password: SSH password (defaults to BATTLEGROUND_PASSWORD env var).

    Returns:
        CommandResult with stdout, stderr, exit_code, timing info.
    """
    if password is None:
        password = os.environ.get("BATTLEGROUND_PASSWORD", "SecureAdmin1")

    start_ms = int(time.time() * 1000)
    client = _get_ssh_client()

    try:
        client.connect(
            hostname=hostname,
            username=username,
            password=password,
            timeout=10,
            look_for_keys=False,
            allow_agent=False,
        )

        _stdin, _stdout, _stderr = client.exec_command(command, timeout=timeout)
        channel = _stdout.channel

        # Wait for command to complete (with timeout)
        channel.settimeout(timeout)
        try:
            stdout_text = _stdout.read().decode("utf-8", errors="replace")
            stderr_text = _stderr.read().decode("utf-8", errors="replace")
            exit_code = channel.recv_exit_status()
            timed_out = False
        except Exception:
            stdout_text = ""
            stderr_text = "Command timed out"
            exit_code = -1
            timed_out = True
            channel.close()

        # Truncate to prevent context explosion
        stdout_text = stdout_text[:MAX_OUTPUT_CHARS]
        stderr_text = stderr_text[:MAX_OUTPUT_CHARS]

        elapsed_ms = int(time.time() * 1000) - start_ms
        return CommandResult(
            stdout=stdout_text.strip(),
            stderr=stderr_text.strip(),
            exit_code=exit_code,
            timed_out=timed_out,
            execution_time_ms=elapsed_ms,
        )

    except Exception as exc:
        elapsed_ms = int(time.time() * 1000) - start_ms
        return CommandResult(
            stdout="",
            stderr=f"SSH connection error: {exc}",
            exit_code=-1,
            timed_out=False,
            execution_time_ms=elapsed_ms,
        )
    finally:
        client.close()
