"""Reusable Rich renderables for the CyberSec AI Capstone terminal dashboard."""

from __future__ import annotations

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

def build_header(phase: str, game_id: int) -> Panel:
    """Centered title panel with phase name and game ID."""
    content = Text(justify="center")
    content.append("CYBERSEC AI CAPSTONE", style="bold white")
    content.append("  —  LIVE GAME", style="bold bright_white")
    content.append(f"\nPhase: ", style="dim white")
    content.append(phase.upper(), style="bold cyan")
    content.append(f"   Game ID: ", style="dim white")
    content.append(str(game_id), style="bold yellow")
    return Panel(Align.center(content), style="white on grey15", border_style="bright_white")


# ---------------------------------------------------------------------------
# Scoreboard
# ---------------------------------------------------------------------------

def build_scoreboard(
    red_score: int,
    blue_score: int,
    turn: int,
    max_turns: int,
    phase: str,
) -> Table:
    """Rich Table titled SCOREBOARD with team scores, turn count, and phase."""
    table = Table(
        title="[bold white]SCOREBOARD[/bold white]",
        show_header=True,
        header_style="bold white",
        border_style="bright_white",
        expand=True,
    )
    table.add_column("Team", style="bold", justify="left")
    table.add_column("Score", style="bold", justify="right")

    table.add_row(
        Text("Red Team", style="bold red"),
        Text(str(red_score), style="bold red"),
    )
    table.add_row(
        Text("Blue Team", style="bold blue"),
        Text(str(blue_score), style="bold blue"),
    )
    table.add_row(
        Text("Turn", style="dim white"),
        Text(f"{turn} / {max_turns}", style="white"),
    )
    table.add_row(
        Text("Phase", style="dim white"),
        build_phase_indicator(phase),
    )
    return table


# ---------------------------------------------------------------------------
# Agent panel
# ---------------------------------------------------------------------------

def build_agent_panel(role: str, actions: list[dict], status: str = "idle") -> Panel:
    """Panel showing last 5 agent actions with status indicator.

    Args:
        role: "red" or "blue"
        actions: list of decision dicts from the orchestrator
        status: "thinking" | "executing" | "idle"
    """
    role_lower = role.lower()
    border_color = "red" if role_lower == "red" else "blue"
    title_text = "RED AGENT" if role_lower == "red" else "BLUE AGENT"

    # Status line
    if status == "thinking":
        status_text = Text("⟳ THINKING...", style=f"bold {border_color}")
    elif status == "executing":
        status_text = Text("▶ EXECUTING", style=f"bold {'bright_red' if role_lower == 'red' else 'bright_blue'}")
    else:
        status_text = Text("● IDLE", style="dim white")

    content = Text()
    content.append_text(status_text)
    content.append("\n\n")

    # Last 5 actions
    recent = actions[-5:] if len(actions) > 5 else actions
    if not recent:
        content.append("No actions recorded yet.", style="dim white")
    else:
        for i, action in enumerate(reversed(recent)):
            cmd = action.get("command", action.get("action", "unknown"))
            stdout = action.get("stdout", action.get("result", ""))
            if stdout and len(stdout) > 200:
                stdout = stdout[:200] + "…"
            age_style = "white" if i == 0 else "dim white"
            content.append(f"[{len(recent) - i}] ", style=f"bold {border_color}")
            content.append(f"{cmd}\n", style=age_style)
            if stdout:
                content.append(f"    {stdout}\n", style="dim")

    return Panel(
        content,
        title=f"[bold {border_color}]{title_text}[/bold {border_color}]",
        border_style=border_color,
        expand=True,
    )


# ---------------------------------------------------------------------------
# Phase indicator
# ---------------------------------------------------------------------------

def build_phase_indicator(phase: str) -> Text:
    """Rich Text showing current game phase with color coding."""
    phase_lower = phase.lower()
    if phase_lower in ("setup", "not_started"):
        style = "bold yellow"
    elif phase_lower in ("battle", "active", "recon", "exploit", "persist", "exfil"):
        style = "bold red"
    elif phase_lower in ("conclusion", "game_over", "complete", "done"):
        style = "bold green"
    else:
        style = "bold cyan"
    return Text(phase.upper(), style=style)


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

def build_footer() -> Panel:
    """Footer panel with exit instructions."""
    return Panel(
        Align.center(Text("Press Ctrl+C to exit", style="dim white")),
        border_style="grey50",
        height=3,
    )
