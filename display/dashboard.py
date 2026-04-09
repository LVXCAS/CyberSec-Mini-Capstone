"""Rich Live terminal dashboard — polls orchestrator API and renders a 3-column layout."""

from __future__ import annotations

import argparse
import time

import requests
from rich.layout import Layout
from rich.live import Live

from display.components import (
    build_agent_panel,
    build_footer,
    build_header,
    build_scoreboard,
)


# ---------------------------------------------------------------------------
# Layout factory
# ---------------------------------------------------------------------------

def make_layout() -> Layout:
    """Build the 3-column dashboard layout.

    Structure:
        header   (size=3)
        body
          red    (ratio=1)
          scores (ratio=1)
          blue   (ratio=1)
        footer   (size=3)
    """
    layout = Layout(name="root")
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )
    layout["body"].split_row(
        Layout(name="red", ratio=1),
        Layout(name="scores", ratio=1),
        Layout(name="blue", ratio=1),
    )
    return layout


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

_FALLBACK_STATUS: dict = {
    "phase": "unknown",
    "elapsed": 0,
    "scores": {"red": 0, "blue": 0},
    "red_kill_chain": [],
    "win_condition": {"game_over": False, "reason": ""},
}


def fetch_game_status(base_url: str) -> dict:
    """GET {base_url}/game/status; return fallback dict on any connection error."""
    try:
        resp = requests.get(f"{base_url}/game/status", timeout=2)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return dict(_FALLBACK_STATUS)


def fetch_agent_actions(base_url: str, role: str, limit: int = 5) -> list[dict]:
    """GET {base_url}/decisions/{role}?n={limit}; return empty list on error."""
    try:
        resp = requests.get(f"{base_url}/decisions/{role}", params={"n": limit}, timeout=2)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Status inference
# ---------------------------------------------------------------------------

_ACTIVE_PHASES = {"battle", "active", "recon", "exploit", "persist", "exfil"}


def _infer_status(actions: list[dict], phase: str) -> str:
    """Return 'executing' | 'thinking' | 'idle' based on last action timestamp."""
    if not actions:
        return "thinking" if phase.lower() in _ACTIVE_PHASES else "idle"

    last = actions[-1]
    ts = last.get("timestamp") or last.get("created_at") or last.get("ts")
    if ts is not None:
        try:
            age = time.time() - float(ts)
            if age < 5:
                return "executing"
        except (TypeError, ValueError):
            pass

    return "thinking" if phase.lower() in _ACTIVE_PHASES else "idle"


# ---------------------------------------------------------------------------
# Main dashboard loop
# ---------------------------------------------------------------------------

def run_dashboard(base_url: str = "http://localhost:8000", refresh_rate: float = 1.0) -> None:
    """Poll orchestrator API and render a live 3-column Rich layout.

    Args:
        base_url: Base URL of the orchestrator (no trailing slash).
        refresh_rate: Seconds between API polls.
    """
    layout = make_layout()

    # Provide initial placeholder content so Live doesn't error before first poll
    _apply_layout(layout, _FALLBACK_STATUS, [], [], game_id=0)

    try:
        with Live(layout, refresh_per_second=4, screen=True) as live:
            game_id = 0
            while True:
                status = fetch_game_status(base_url)
                red_actions = fetch_agent_actions(base_url, "red")
                blue_actions = fetch_agent_actions(base_url, "blue")

                phase = status.get("phase", "unknown")
                scores = status.get("scores", {"red": 0, "blue": 0})

                # Derive game_id from win condition or keep incrementing
                if status.get("win_condition", {}).get("game_over"):
                    game_id = max(game_id, 1)

                _apply_layout(layout, status, red_actions, blue_actions, game_id=game_id)

                time.sleep(refresh_rate)
    except KeyboardInterrupt:
        pass


def _apply_layout(
    layout: Layout,
    status: dict,
    red_actions: list[dict],
    blue_actions: list[dict],
    game_id: int,
) -> None:
    """Update all layout panels with current data."""
    phase = status.get("phase", "unknown")
    scores = status.get("scores", {"red": 0, "blue": 0})
    red_score = scores.get("red", 0)
    blue_score = scores.get("blue", 0)

    # Turn count — use elapsed as a proxy if turn not provided
    turn = status.get("turn", status.get("elapsed", 0))
    max_turns = status.get("max_turns", 20)

    red_status = _infer_status(red_actions, phase)
    blue_status = _infer_status(blue_actions, phase)

    layout["header"].update(build_header(phase, game_id))
    layout["footer"].update(build_footer())
    layout["red"].update(build_agent_panel("red", red_actions, status=red_status))
    layout["blue"].update(build_agent_panel("blue", blue_actions, status=blue_status))
    layout["scores"].update(
        build_scoreboard(red_score, blue_score, int(turn), max_turns, phase)
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CyberSec AI Capstone — Live Terminal Dashboard")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Orchestrator base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--refresh",
        type=float,
        default=1.0,
        help="Seconds between API polls (default: 1.0)",
    )
    args = parser.parse_args()
    run_dashboard(base_url=args.url, refresh_rate=args.refresh)
