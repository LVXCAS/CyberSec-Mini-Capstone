---
phase: "03"
plan: "03"
subsystem: display
tags: [rich, replay, terminal, dashboard, cli]

dependency-graph:
  requires: ["03-01"]
  provides: ["display/replay.py", "replay_game CLI"]
  affects: ["03-04"]

tech-stack:
  added: []
  patterns: ["chronological decision merge-sort", "clamped inter-event delay", "immutable action list accumulation"]

key-files:
  created:
    - display/replay.py
  modified: []

decisions:
  - choice: "Clamp delay to 0.1–3.0 s regardless of speed multiplier"
    rationale: "Keeps replay watchable even for games with burst or sparse decisions"
  - choice: "Inject _role key into each decision dict (shallow copy)"
    rationale: "Avoids mutating orchestrator response; allows single merged list to track team ownership"
  - choice: "Fallback sort key priority: timestamp > id > insertion order"
    rationale: "Handles cases where orchestrator returns decisions without timestamps"

metrics:
  tasks-completed: 1
  tasks-total: 1
  deviations: 0
  duration: "~4 minutes"
  completed: "2026-04-09"
---

# Phase 3 Plan 03: Replay Viewer Summary

**One-liner:** Post-game CLI replay of decision log using Rich Live with per-decision timing and adjustable speed multiplier.

## What Was Built

`display/replay.py` provides a terminal replay viewer that:

1. Fetches all red and blue decisions from the orchestrator (`GET /decisions/{role}?n=9999`) and merges them into a chronological list.
2. Displays each decision in sequence using the same Rich `Live` + `make_layout()` rendering pipeline as the live dashboard.
3. Applies per-decision delays derived from actual timestamps divided by the `--speed` multiplier, clamped to `[0.1, 3.0]` seconds.
4. Shows "REPLAY COMPLETE" in the header after the last decision and blocks until Ctrl+C.
5. Prints a descriptive error panel (no plain `print()`) when no decisions are found.

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Clamp delay 0.1–3.0 s | Watchable regardless of real-game timing gaps |
| Shallow-copy + `_role` injection | Immutable pattern; single list routing |
| Fallback sort: timestamp → id → order | Robust to incomplete orchestrator data |

## Deviations from Plan

None — plan executed exactly as written.

## Verification

```
python3 -c "from display.replay import fetch_all_decisions, replay_game; print('OK')"
# => OK

python3 -c "
from display.replay import fetch_all_decisions
decisions = fetch_all_decisions('http://localhost:1')
assert decisions == []
print('graceful error: OK')
"
# => graceful error: OK
```

## Commits

| Hash | Message |
|------|---------|
| 67c7bbe | feat(03-03): add post-game replay viewer CLI |
