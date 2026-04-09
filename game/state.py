"""Game state machine: phases, context, win conditions, transitions."""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Optional


class GamePhase(Enum):
    SETUP = "setup"
    BATTLE = "battle"
    CONCLUSION = "conclusion"


_PHASE_ORDER = [GamePhase.SETUP, GamePhase.BATTLE, GamePhase.CONCLUSION]


@dataclass
class GameContext:
    """Mutable game context -- use replace() for immutable-style updates."""

    phase: GamePhase = GamePhase.SETUP
    start_time: float = 0.0
    setup_duration: int = 300       # 5 minutes
    battle_duration: int = 1200     # 20 minutes
    red_kill_chain: list[str] = field(default_factory=list)
    blue_lockout: bool = False
    service_down_since: dict[str, float] = field(default_factory=dict)


# Full kill chain steps in order
KILL_CHAIN_STEPS = ("recon", "exploit", "privesc", "persist")

# Seconds a critical service can be down before triggering loss
SERVICE_DOWN_THRESHOLD = 120.0


def check_win_condition(
    ctx: GameContext,
    scores: dict,
) -> tuple[bool, str]:
    """Return (game_over, reason) based on current context and scores.

    Win conditions checked:
    1. Time expiry (setup or battle duration exceeded)
    2. Red full kill chain achieved
    3. Blue lockout achieved (red fully blocked)
    4. Critical service down > 120 s
    """
    now = time.monotonic()
    elapsed = now - ctx.start_time if ctx.start_time > 0 else 0

    # 1 -- Time expiry
    if ctx.phase == GamePhase.SETUP and elapsed >= ctx.setup_duration:
        return True, "Setup time expired"
    if ctx.phase == GamePhase.BATTLE and elapsed >= ctx.battle_duration:
        return True, "Battle time expired"

    # 2 -- Red full kill chain
    if all(step in ctx.red_kill_chain for step in KILL_CHAIN_STEPS):
        return True, "Red completed full kill chain"

    # 3 -- Blue lockout
    if ctx.blue_lockout:
        return True, "Blue achieved full lockout of red"

    # 4 -- Critical service down too long
    for svc, down_since in ctx.service_down_since.items():
        if (now - down_since) >= SERVICE_DOWN_THRESHOLD:
            return True, f"Critical service '{svc}' down for >{SERVICE_DOWN_THRESHOLD}s"

    return False, ""


def advance_phase(ctx: GameContext) -> GameContext:
    """Return a new GameContext with the phase advanced one step."""
    idx = _PHASE_ORDER.index(ctx.phase)
    if idx >= len(_PHASE_ORDER) - 1:
        return ctx  # already at conclusion
    return replace(ctx, phase=_PHASE_ORDER[idx + 1], start_time=time.monotonic())
