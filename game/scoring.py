"""Scoring engine: point awards, stealth/detection bonuses, kill chain tracking."""

from __future__ import annotations

from typing import Callable, Optional

# Competitive points
POINT_VALUES: dict[str, int] = {
    # Red team actions
    "recon_complete": 5,
    "service_exploited": 15,
    "privesc_achieved": 20,
    "persistence_installed": 20,
    "full_kill_chain": 40,
    # Blue team actions
    "vuln_patched": 10,
    "attack_detected": 10,
    "attacker_blocked": 15,
    "service_kept_up": 5,
    "lockout_achieved": 40,
    # AI reasoning quality bonuses
    "red_undetected_action": 5,
    "blue_detected_stealthily": 5,
    "pivot_on_failure": 3,
    "correct_inference": 3,
    "adaptive_escalation": 5,
}

# Kill chain steps that count toward full_kill_chain bonus
_KILL_CHAIN_MAP: dict[str, str] = {
    "recon_complete": "recon",
    "service_exploited": "exploit",
    "privesc_achieved": "privesc",
    "persistence_installed": "persist",
}

# Two-turn stealth window: if red acts undetected within this many turns, bonus
STEALTH_WINDOW = 2


class ScoringEngine:
    """Track and award points for both teams."""

    def __init__(self, db_log_fn: Callable[..., None]) -> None:
        self._db_log = db_log_fn
        self._red_score: int = 0
        self._blue_score: int = 0
        self._events: list[dict] = []
        self._kill_chain_achieved: set[str] = set()
        # Track last red action turn and last blue detection turn for stealth
        self._last_red_action_turn: int = 0
        self._last_blue_detect_turn: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def award(
        self,
        agent_role: str,
        event_type: str,
        description: str,
        turn_number: int,
    ) -> int:
        """Award points for *event_type*. Returns points awarded."""
        points = POINT_VALUES.get(event_type, 0)
        if points == 0:
            return 0

        if agent_role == "red":
            self._red_score += points
            self._last_red_action_turn = turn_number
        else:
            self._blue_score += points
            if event_type in ("attack_detected", "attacker_blocked"):
                self._last_blue_detect_turn = turn_number

        event = {
            "agent_role": agent_role,
            "event_type": event_type,
            "points": points,
            "description": description,
            "turn_number": turn_number,
        }
        self._events.append(event)
        self._db_log(**event)

        # Auto-check kill chain progress
        if agent_role == "red" and event_type in _KILL_CHAIN_MAP:
            self._kill_chain_achieved.add(_KILL_CHAIN_MAP[event_type])

        return points

    def check_stealth_bonus(self, turn_number: int) -> Optional[int]:
        """Award red stealth bonus if last red action was undetected within window."""
        if self._last_red_action_turn == 0:
            return None
        gap = turn_number - self._last_red_action_turn
        if gap <= STEALTH_WINDOW and self._last_blue_detect_turn < self._last_red_action_turn:
            pts = self.award("red", "red_undetected_action", "Stealth bonus", turn_number)
            return pts
        return None

    def check_kill_chain_progress(self) -> tuple[set[str], bool]:
        """Return (achieved_steps, is_complete)."""
        full = {"recon", "exploit", "privesc", "persist"}
        return self._kill_chain_achieved, self._kill_chain_achieved >= full

    def get_totals(self) -> dict[str, int]:
        """Return current score totals."""
        return {"red": self._red_score, "blue": self._blue_score}
