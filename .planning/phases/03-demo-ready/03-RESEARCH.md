# Phase 3: Demo Ready - Research

**Researched:** 2026-04-08
**Domain:** Terminal UI (Rich), Docker reset scripting, presentation
**Confidence:** HIGH

## Summary

Phase 3 wraps a working game (Phase 2) in demo-quality presentation layers: a Rich terminal dashboard showing real-time game progress, a one-command reset script for reliable demos, a log replay viewer, and capstone slides. All required libraries (Rich, SQLite) are already in the stack. The data layer (decision_log, score_events, snapshots tables) provides everything needed for both live display and replay.

**Primary recommendation:** Build a single `display.py` module using Rich Live + Layout + Table for the real-time dashboard, a `replay.py` CLI that reads decision_log rows and renders them with simulated timing, and a `reset.sh` that does `docker compose down -v && docker compose up --build -d` with health checks.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| rich | 13.x | Terminal dashboard, tables, panels, live display | Already chosen; best Python terminal UI library |
| sqlite3 | stdlib | Read decision_log/score_events for replay | Already in use |
| docker compose | v2 | Reset/start via CLI | Already in use |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| rich.live | (part of rich) | Auto-refreshing terminal layout | Real-time game display |
| rich.layout | (part of rich) | Split-pane terminal layout | Side-by-side red/blue panels |
| rich.table | (part of rich) | Score tables | Scoreboard display |
| rich.panel | (part of rich) | Bordered sections | Agent action panels |
| time.sleep | stdlib | Simulated timing in replay | Replay viewer |
| argparse | stdlib | CLI for replay viewer | `python replay.py --game-id 1 --speed 2x` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Rich Live | textual (TUI framework) | Overkill; Rich Live is sufficient for read-only dashboard |
| Custom replay | asciinema | Would need recording during game; post-hoc replay from DB is simpler |

## Architecture Patterns

### Recommended Project Structure
```
display/
  dashboard.py      # Rich Live layout for real-time game monitoring
  replay.py         # CLI replay viewer reading from SQLite
  components.py     # Reusable Rich renderables (scoreboard, action log, status)
scripts/
  reset.sh          # docker compose down -v && up --build with validation
  start.sh          # docker compose up -d + wait for health + launch dashboard
  demo.sh           # reset + start combined for presentation
presentation/
  slides.md         # Slide content (or .pptx)
  architecture.png  # Architecture diagram
```

### Pattern 1: Rich Live Dashboard
**What:** A `Live` context manager that refreshes a `Layout` every 1-2 seconds by polling the orchestrator API or SQLite directly.
**When to use:** Real-time game display (PRES-01).
**Example:**
```python
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table

def make_layout() -> Layout:
    layout = Layout()
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

def run_dashboard(db_path: str, refresh_rate: float = 1.0):
    layout = make_layout()
    with Live(layout, refresh_per_second=int(1/refresh_rate), screen=True):
        while True:
            # Poll DB for latest state
            layout["header"].update(Panel("CYBER CAPSTONE - LIVE GAME"))
            layout["red"].update(build_agent_panel("red", db_path))
            layout["blue"].update(build_agent_panel("blue", db_path))
            layout["scores"].update(build_scoreboard(db_path))
            time.sleep(refresh_rate)
```

### Pattern 2: Replay from Decision Log
**What:** Read all decision_log rows for a game, then iterate with `time.sleep()` between entries, rendering each action through the same Rich components.
**When to use:** Post-game replay (PRES-03).
**Example:**
```python
import sqlite3, time
from rich.live import Live

def replay_game(db_path: str, speed: float = 1.0):
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT * FROM decision_log ORDER BY id"
    ).fetchall()

    layout = make_layout()
    with Live(layout, screen=True):
        prev_ts = None
        for row in rows:
            if prev_ts:
                delay = (parse_ts(row.timestamp) - prev_ts).total_seconds()
                time.sleep(delay / speed)
            update_layout_with_action(layout, row)
            prev_ts = parse_ts(row.timestamp)
```

### Pattern 3: Reset Script with Validation
**What:** Bash script that tears down all containers/volumes and rebuilds, then verifies health.
```bash
#!/usr/bin/env bash
set -euo pipefail
echo "Tearing down..."
docker compose down -v --remove-orphans
echo "Rebuilding..."
docker compose up --build -d
echo "Waiting for health..."
for svc in orchestrator battleground; do
  timeout 60 bash -c "until docker inspect --format='{{.State.Health.Status}}' $svc 2>/dev/null | grep -q healthy; do sleep 2; done"
done
echo "Ready."
```

### Anti-Patterns to Avoid
- **Polling too fast:** Rich Live at >4 fps wastes CPU; 1-2 fps is plenty for a demo.
- **Reading SQLite from container without volume mount:** The DB is in `orchestrator-data` volume; mount it read-only for the dashboard or poll via API.
- **Not using `screen=True`:** Without it, Rich Live appends rather than replacing -- looks terrible for a dashboard.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Terminal layout/panels | ANSI escape codes | `rich.layout.Layout` | Handles terminal resize, color, borders |
| Progress bars | Custom counters | `rich.progress.Progress` | Turn progress bar for game phases |
| Tables | String formatting | `rich.table.Table` | Auto-column-width, borders, colors |
| Terminal clearing | `os.system("clear")` | `Live(screen=True)` | Proper alternate screen buffer |

## Common Pitfalls

### Pitfall 1: SQLite Locked During Game
**What goes wrong:** Dashboard reads SQLite while orchestrator writes; "database is locked" errors.
**Why it happens:** SQLite default locking with concurrent access from different processes.
**How to avoid:** Either (a) poll via HTTP API endpoints on orchestrator (preferred), or (b) open SQLite in `?mode=ro` read-only mode with WAL journal mode enabled on the writer.
**Warning signs:** Intermittent crashes in dashboard during active game.

### Pitfall 2: Docker Volume Not Cleaned
**What goes wrong:** `docker compose down` without `-v` leaves the SQLite volume; next game starts with stale data.
**How to avoid:** Always `docker compose down -v`. The reset script MUST include `-v`.
**Warning signs:** Second run shows scores/logs from first run.

### Pitfall 3: Rich Live + Print Statements
**What goes wrong:** Any `print()` during a `Live` context corrupts the display.
**How to avoid:** Use `live.console.log()` or Rich's built-in logging handler.
**Warning signs:** Garbled terminal output during game.

### Pitfall 4: Demo Machine Performance
**What goes wrong:** KoboldCpp inference is slow; audience stares at idle screen.
**How to avoid:** Show the dashboard updating in real time with status indicators ("Red Agent thinking...", "Executing command..."). Use Rich spinners.
**Warning signs:** Long periods with no visible activity.

## Code Examples

### Scoreboard Table
```python
from rich.table import Table

def build_scoreboard(red_score: int, blue_score: int, turn: int, max_turns: int) -> Table:
    table = Table(title="SCOREBOARD", show_header=True)
    table.add_column("Team", style="bold")
    table.add_column("Score", justify="right")
    table.add_row("[red]Red Team[/red]", f"[red]{red_score}[/red]")
    table.add_row("[blue]Blue Team[/blue]", f"[blue]{blue_score}[/blue]")
    table.add_row("Turn", f"{turn}/{max_turns}")
    return table
```

### Agent Action Panel
```python
from rich.panel import Panel
from rich.text import Text

def build_agent_panel(role: str, last_action: dict) -> Panel:
    color = "red" if role == "red" else "blue"
    content = Text()
    content.append(f"Skill: {last_action.get('command', 'waiting...')}\n", style="bold")
    content.append(f"Result: {last_action.get('result_stdout', '')[:200]}\n")
    return Panel(content, title=f"[{color}]{role.upper()} AGENT[/{color}]", border_style=color)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| curses-based TUI | Rich Live + Layout | Rich 10+ (2021) | Much simpler code, better rendering |
| Manual ANSI codes | Rich markup `[red]text[/red]` | Rich 1.0 | No platform compatibility issues |

## Open Questions

1. **Dashboard data source: API vs direct SQLite?**
   - API is cleaner (no volume mount needed for dashboard process) but requires adding a few GET endpoints if they don't exist.
   - Direct SQLite read is simpler if dashboard runs on host with volume access.
   - Recommendation: Use existing `/game/*` API endpoints; add any missing ones.

2. **Slide format**
   - Google Slides, PowerPoint, or Marp (markdown-to-slides)?
   - Recommendation: Whatever the user prefers. Marp is fastest to create from markdown.

## Sources

### Primary (HIGH confidence)
- Rich library: well-known, stable API. Layout/Live/Table are core features since v10+.
- Docker Compose v2: `down -v` behavior is standard and documented.
- Existing codebase: decision_log, score_events tables confirmed in orchestrator/db.py.

### Secondary (MEDIUM confidence)
- SQLite WAL mode for concurrent reads: standard SQLite documentation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Rich is already chosen, patterns are well-established
- Architecture: HIGH - straightforward polling dashboard + DB replay
- Pitfalls: HIGH - common issues with Rich Live and Docker volumes are well-documented

**Research date:** 2026-04-08
**Valid until:** 2026-05-08 (stable domain)
