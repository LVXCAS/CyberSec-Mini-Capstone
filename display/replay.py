"""Post-game replay viewer — renders a completed game's decision log with simulated timing.

Run as:
    python -m display.replay [--url URL] [--speed SPEED]
"""

from __future__ import annotations

import argparse
import time

import requests
from rich.align import Align
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from display.components import (
    build_agent_panel,
    build_footer,
    build_header,
    build_scoreboard,
)
from display.dashboard import make_layout


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def fetch_all_decisions(base_url: str) -> list[dict]:
    """Fetch all decisions for red and blue, merge and sort chronologically.

    Returns:
        Combined list of decision dicts sorted by timestamp (ascending).
        Each dict retains an injected ``_role`` key (``"red"`` or ``"blue"``).
    """
    decisions: list[dict] = []
    for role in ("red", "blue"):
        try:
            resp = requests.get(
                f"{base_url}/decisions/{role}",
                params={"n": 9999},
                timeout=5,
            )
            resp.raise_for_status()
            role_decisions = resp.json()
            for d in role_decisions:
                d = dict(d)          # shallow copy — preserve immutability
                d["_role"] = role
                decisions.append(d)
        except Exception:
            pass

    # Sort by timestamp field; fall back to id then insertion order
    def _sort_key(d: dict) -> float:
        ts = d.get("timestamp") or d.get("created_at") or d.get("ts")
        if ts is not None:
            try:
                return float(ts)
            except (TypeError, ValueError):
                pass
        decision_id = d.get("id") or d.get("decision_id")
        if decision_id is not None:
            try:
                return float(decision_id)
            except (TypeError, ValueError):
                pass
        return 0.0

    decisions.sort(key=_sort_key)
    return decisions


def _fetch_game_status(base_url: str) -> dict:
    """GET /game/status; return empty dict on error."""
    try:
        resp = requests.get(f"{base_url}/game/status", timeout=2)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def _build_replay_header(phase: str, game_id: int, index: int, total: int) -> Panel:
    """Header panel augmented with replay progress indicator."""
    content = Text(justify="center")
    content.append("CYBERSEC AI CAPSTONE", style="bold white")
    content.append("  —  REPLAY MODE", style="bold bright_cyan")
    content.append(f"\nPhase: ", style="dim white")
    content.append(phase.upper(), style="bold cyan")
    content.append(f"   Game ID: ", style="dim white")
    content.append(str(game_id), style="bold yellow")
    content.append(f"   Decision: ", style="dim white")
    content.append(f"{index}/{total}", style="bold magenta")
    return Panel(Align.center(content), style="white on grey15", border_style="bright_cyan")


def _build_complete_header(phase: str, game_id: int) -> Panel:
    """Header shown after all decisions have been replayed."""
    content = Text(justify="center")
    content.append("CYBERSEC AI CAPSTONE", style="bold white")
    content.append("  —  REPLAY COMPLETE", style="bold bright_green")
    content.append(f"\nPhase: ", style="dim white")
    content.append(phase.upper(), style="bold cyan")
    content.append(f"   Game ID: ", style="dim white")
    content.append(str(game_id), style="bold yellow")
    content.append(f"   Press Ctrl+C to exit", style="dim white")
    return Panel(Align.center(content), style="white on grey15", border_style="bright_green")


# ---------------------------------------------------------------------------
# Main replay loop
# ---------------------------------------------------------------------------

def replay_game(base_url: str = "http://localhost:8000", speed: float = 1.0) -> None:
    """Replay a completed game's decision log with simulated timing.

    Args:
        base_url: Orchestrator base URL (no trailing slash).
        speed:    Playback speed multiplier — 2.0 = twice as fast, 0.5 = half speed.
    """
    decisions = fetch_all_decisions(base_url)

    if not decisions:
        from rich.console import Console
        console = Console()
        console.print(
            Panel(
                "[bold yellow]No game data found.[/bold yellow]\n"
                f"Could not retrieve decisions from [cyan]{base_url}[/cyan].\n"
                "Ensure the orchestrator is running and a game has been played.",
                title="[bold red]Replay Error[/bold red]",
                border_style="red",
            )
        )
        return

    status = _fetch_game_status(base_url)
    phase = status.get("phase", "game_over")
    scores = status.get("scores", {"red": 0, "blue": 0})
    red_score = scores.get("red", 0)
    blue_score = scores.get("blue", 0)
    turn = status.get("turn", status.get("elapsed", len(decisions)))
    max_turns = status.get("max_turns", 20)
    game_id = status.get("game_id", 1)

    layout = make_layout()
    red_actions: list[dict] = []
    blue_actions: list[dict] = []
    total = len(decisions)

    # Seed layout with empty state before entering Live
    layout["header"].update(_build_replay_header(phase, game_id, 0, total))
    layout["footer"].update(build_footer())
    layout["red"].update(build_agent_panel("red", red_actions, status="idle"))
    layout["blue"].update(build_agent_panel("blue", blue_actions, status="idle"))
    layout["scores"].update(build_scoreboard(red_score, blue_score, 0, max_turns, phase))

    prev_ts: float | None = None

    try:
        with Live(layout, refresh_per_second=8, screen=True):
            for idx, decision in enumerate(decisions, start=1):
                # --- Calculate and apply inter-decision delay ---
                ts = decision.get("timestamp") or decision.get("created_at") or decision.get("ts")
                if ts is not None and prev_ts is not None:
                    try:
                        raw_delay = (float(ts) - prev_ts) / speed
                        delay = min(max(raw_delay, 0.1), 3.0)
                    except (TypeError, ValueError):
                        delay = 0.5 / speed
                else:
                    delay = 0.5 / speed

                time.sleep(delay)

                if ts is not None:
                    try:
                        prev_ts = float(ts)
                    except (TypeError, ValueError):
                        pass

                # --- Route decision to the correct agent list ---
                role = decision.get("_role", "red")
                if role == "red":
                    red_actions = [*red_actions, decision]
                else:
                    blue_actions = [*blue_actions, decision]

                # --- Update layout panels ---
                layout["header"].update(_build_replay_header(phase, game_id, idx, total))
                layout["red"].update(build_agent_panel("red", red_actions, status="idle"))
                layout["blue"].update(build_agent_panel("blue", blue_actions, status="idle"))

                # Refresh scores — use cumulative count as surrogate turn if not available
                turn_now = int(turn) if turn else idx
                layout["scores"].update(
                    build_scoreboard(red_score, blue_score, turn_now, max_turns, phase)
                )

            # --- Replay complete ---
            layout["header"].update(_build_complete_header(phase, game_id))

            # Block until Ctrl+C
            while True:
                time.sleep(0.5)

    except KeyboardInterrupt:
        pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="CyberSec AI Capstone — Post-Game Replay Viewer"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Orchestrator base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Playback speed multiplier (default: 1.0 — e.g. 2.0 for 2x speed)",
    )
    args = parser.parse_args()
    replay_game(base_url=args.url, speed=args.speed)
