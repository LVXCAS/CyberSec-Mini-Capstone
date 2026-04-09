"""SQLite database for logging all orchestrator actions."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

DB_PATH = os.environ.get("ORCHESTRATOR_DB_PATH", "/app/data/game.db")

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS decision_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    agent_role TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    command TEXT NOT NULL,
    reasoning TEXT,
    result_stdout TEXT,
    result_stderr TEXT,
    exit_code INTEGER,
    was_blocked INTEGER NOT NULL DEFAULT 0,
    block_reason TEXT
);

CREATE TABLE IF NOT EXISTS safety_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    agent_role TEXT NOT NULL,
    command TEXT NOT NULL,
    allowed INTEGER NOT NULL,
    reason TEXT
);

CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    agent_role TEXT NOT NULL,
    finding_type TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL,
    raw_data TEXT
);

CREATE TABLE IF NOT EXISTS game_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    phase TEXT NOT NULL,
    red_score INTEGER NOT NULL DEFAULT 0,
    blue_score INTEGER NOT NULL DEFAULT 0,
    turn_count INTEGER NOT NULL DEFAULT 0,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS score_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    agent_role TEXT NOT NULL,
    event_type TEXT NOT NULL,
    points INTEGER NOT NULL,
    description TEXT,
    turn_number INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    snapshot_data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS game_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    value TEXT
);
"""


def _get_connection() -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode enabled."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize database schema."""
    conn = _get_connection()
    try:
        conn.executescript(_CREATE_TABLES)
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_decision(
    agent_role: str,
    turn_number: int,
    command: str,
    reasoning: str = "",
    result_stdout: str = "",
    result_stderr: str = "",
    exit_code: int = 0,
    was_blocked: bool = False,
    block_reason: Optional[str] = None,
) -> None:
    """Log an agent command decision."""
    conn = _get_connection()
    try:
        conn.execute(
            """INSERT INTO decision_log
               (timestamp, agent_role, turn_number, command, reasoning,
                result_stdout, result_stderr, exit_code, was_blocked, block_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                _now(),
                agent_role,
                turn_number,
                command,
                reasoning,
                result_stdout,
                result_stderr,
                exit_code,
                1 if was_blocked else 0,
                block_reason,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def log_safety_check(
    agent_role: str,
    command: str,
    allowed: bool,
    reason: Optional[str] = None,
) -> None:
    """Log a safety filter check."""
    conn = _get_connection()
    try:
        conn.execute(
            """INSERT INTO safety_log
               (timestamp, agent_role, command, allowed, reason)
               VALUES (?, ?, ?, ?, ?)""",
            (_now(), agent_role, command, 1 if allowed else 0, reason),
        )
        conn.commit()
    finally:
        conn.close()


def log_finding(
    agent_role: str,
    finding_type: str,
    description: str,
    severity: str,
    raw_data: str = "",
) -> None:
    """Log a finding discovered by an agent."""
    conn = _get_connection()
    try:
        conn.execute(
            """INSERT INTO findings
               (timestamp, agent_role, finding_type, description, severity, raw_data)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (_now(), agent_role, finding_type, description, severity, raw_data),
        )
        conn.commit()
    finally:
        conn.close()


def log_score_event(
    agent_role: str,
    event_type: str,
    points: int,
    description: str,
    turn_number: int,
) -> None:
    """Log a scoring event."""
    conn = _get_connection()
    try:
        conn.execute(
            """INSERT INTO score_events
               (timestamp, agent_role, event_type, points, description, turn_number)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (_now(), agent_role, event_type, points, description, turn_number),
        )
        conn.commit()
    finally:
        conn.close()


def get_scores() -> dict[str, int]:
    """Return aggregate scores: {"red": int, "blue": int}."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            """SELECT agent_role, COALESCE(SUM(points), 0) AS total
               FROM score_events GROUP BY agent_role""",
        ).fetchall()
        result: dict[str, int] = {"red": 0, "blue": 0}
        for row in rows:
            result[row["agent_role"]] = row["total"]
        return result
    finally:
        conn.close()


def log_snapshot(data: str) -> None:
    """Log a battleground state snapshot."""
    conn = _get_connection()
    try:
        conn.execute(
            """INSERT INTO snapshots (timestamp, snapshot_data) VALUES (?, ?)""",
            (_now(), data),
        )
        conn.commit()
    finally:
        conn.close()


def get_score_events(agent_role: Optional[str] = None) -> list[dict]:
    """Get score events, optionally filtered by agent role."""
    conn = _get_connection()
    try:
        if agent_role:
            rows = conn.execute(
                """SELECT * FROM score_events
                   WHERE agent_role = ? ORDER BY id""",
                (agent_role,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM score_events ORDER BY id",
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_recent_decisions(agent_role: str, n: int = 10) -> list[dict]:
    """Get the N most recent decisions for an agent."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM decision_log
               WHERE agent_role = ?
               ORDER BY id DESC LIMIT ?""",
            (agent_role, n),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
