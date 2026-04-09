"""Battleground state snapshot manager."""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Optional

import httpx

logger = logging.getLogger(__name__)

# Diagnostic commands to capture battleground state
_SNAPSHOT_COMMANDS = [
    "ps aux --no-headers",
    "ss -tlnp",
    "cat /etc/passwd | grep -v nologin | grep -v false",
    "iptables -L -n 2>/dev/null || echo 'no iptables'",
    "crontab -l 2>/dev/null || echo 'no crontab'",
]


def take_snapshot(orchestrator_url: str) -> dict:
    """Capture a battleground state snapshot via the orchestrator.

    POSTs diagnostic commands as role 'system' and collects results.
    """
    results: dict[str, str] = {}
    ts = datetime.now(timezone.utc).isoformat()

    for cmd in _SNAPSHOT_COMMANDS:
        try:
            resp = httpx.post(
                f"{orchestrator_url}/execute",
                json={"role": "system", "command": cmd},
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                results[cmd] = data.get("stdout", "")
            else:
                results[cmd] = f"HTTP {resp.status_code}"
        except Exception as exc:  # noqa: BLE001
            results[cmd] = f"error: {exc}"

    return {"timestamp": ts, "commands": results}


class SnapshotManager:
    """Periodically capture battleground snapshots on a daemon thread."""

    def __init__(
        self,
        interval: int = 60,
        orchestrator_url: str = "http://localhost:8000",
        db_log_fn: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._interval = interval
        self._orchestrator_url = orchestrator_url
        self._db_log = db_log_fn
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the snapshot daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("SnapshotManager started (interval=%ds)", self._interval)

    def stop(self) -> None:
        """Signal the snapshot thread to stop."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        logger.info("SnapshotManager stopped")

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                snapshot = take_snapshot(self._orchestrator_url)
                if self._db_log:
                    self._db_log(json.dumps(snapshot))
            except Exception:  # noqa: BLE001
                logger.exception("Snapshot capture failed")
            self._stop_event.wait(timeout=self._interval)
