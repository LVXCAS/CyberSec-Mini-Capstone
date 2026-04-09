"""Unit tests for game engine: state, scoring, and narrative."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from game.state import GamePhase, GameContext, advance_phase, check_win_condition
from game.scoring import ScoringEngine, POINT_VALUES
from game.narrative import generate_narrative


# ---------------------------------------------------------------------------
# GamePhase / GameContext tests
# ---------------------------------------------------------------------------


class TestGamePhase:
    """Test phase transitions and win conditions."""

    def test_phases_exist(self) -> None:
        assert GamePhase.SETUP.value == "setup"
        assert GamePhase.BATTLE.value == "battle"
        assert GamePhase.CONCLUSION.value == "conclusion"

    def test_advance_setup_to_battle(self) -> None:
        ctx = GameContext(phase=GamePhase.SETUP)
        new_ctx = advance_phase(ctx)
        assert new_ctx.phase == GamePhase.BATTLE
        assert new_ctx is not ctx  # immutable-style

    def test_advance_battle_to_conclusion(self) -> None:
        ctx = GameContext(phase=GamePhase.BATTLE)
        new_ctx = advance_phase(ctx)
        assert new_ctx.phase == GamePhase.CONCLUSION

    def test_advance_conclusion_stays(self) -> None:
        ctx = GameContext(phase=GamePhase.CONCLUSION)
        new_ctx = advance_phase(ctx)
        assert new_ctx.phase == GamePhase.CONCLUSION

    def test_full_transition_chain(self) -> None:
        ctx = GameContext(phase=GamePhase.SETUP)
        ctx = advance_phase(ctx)
        assert ctx.phase == GamePhase.BATTLE
        ctx = advance_phase(ctx)
        assert ctx.phase == GamePhase.CONCLUSION


# ---------------------------------------------------------------------------
# Win condition tests
# ---------------------------------------------------------------------------


class TestWinConditions:
    """Test all 4 win conditions."""

    def test_time_expiry_setup(self) -> None:
        ctx = GameContext(
            phase=GamePhase.SETUP,
            start_time=time.monotonic() - 400,
            setup_duration=300,
        )
        game_over, reason = check_win_condition(ctx, {})
        assert game_over is True
        assert "Setup time expired" in reason

    def test_time_expiry_battle(self) -> None:
        ctx = GameContext(
            phase=GamePhase.BATTLE,
            start_time=time.monotonic() - 1300,
            battle_duration=1200,
        )
        game_over, reason = check_win_condition(ctx, {})
        assert game_over is True
        assert "Battle time expired" in reason

    def test_red_full_kill_chain(self) -> None:
        ctx = GameContext(
            phase=GamePhase.BATTLE,
            start_time=time.monotonic(),
            red_kill_chain=["recon", "exploit", "privesc", "persist"],
        )
        game_over, reason = check_win_condition(ctx, {})
        assert game_over is True
        assert "kill chain" in reason.lower()

    def test_blue_lockout(self) -> None:
        ctx = GameContext(
            phase=GamePhase.BATTLE,
            start_time=time.monotonic(),
            blue_lockout=True,
        )
        game_over, reason = check_win_condition(ctx, {})
        assert game_over is True
        assert "lockout" in reason.lower()

    def test_critical_service_down(self) -> None:
        ctx = GameContext(
            phase=GamePhase.BATTLE,
            start_time=time.monotonic(),
            service_down_since={"ssh": time.monotonic() - 200},
        )
        game_over, reason = check_win_condition(ctx, {})
        assert game_over is True
        assert "Critical service" in reason

    def test_no_win_condition(self) -> None:
        ctx = GameContext(
            phase=GamePhase.BATTLE,
            start_time=time.monotonic(),
        )
        game_over, reason = check_win_condition(ctx, {})
        assert game_over is False
        assert reason == ""


# ---------------------------------------------------------------------------
# ScoringEngine tests
# ---------------------------------------------------------------------------


class TestScoringEngine:
    """Test scoring engine point awards and kill chain tracking."""

    def _make_engine(self) -> ScoringEngine:
        return ScoringEngine(db_log_fn=MagicMock())

    def test_award_known_event(self) -> None:
        engine = self._make_engine()
        pts = engine.award("red", "recon_complete", "Scanned ports", 1)
        assert pts == POINT_VALUES["recon_complete"]
        assert engine.get_totals()["red"] == pts

    def test_award_unknown_event(self) -> None:
        engine = self._make_engine()
        pts = engine.award("red", "nonexistent_event", "Nothing", 1)
        assert pts == 0

    def test_award_blue_event(self) -> None:
        engine = self._make_engine()
        pts = engine.award("blue", "vuln_patched", "Patched vuln", 1)
        assert pts == POINT_VALUES["vuln_patched"]
        assert engine.get_totals()["blue"] == pts

    def test_multiple_awards_accumulate(self) -> None:
        engine = self._make_engine()
        engine.award("red", "recon_complete", "Scan", 1)
        engine.award("red", "service_exploited", "SSH bruted", 2)
        totals = engine.get_totals()
        assert totals["red"] == POINT_VALUES["recon_complete"] + POINT_VALUES["service_exploited"]

    def test_check_kill_chain_progress_partial(self) -> None:
        engine = self._make_engine()
        engine.award("red", "recon_complete", "Scan", 1)
        engine.award("red", "service_exploited", "SSH", 2)
        achieved, complete = engine.check_kill_chain_progress()
        assert "recon" in achieved
        assert "exploit" in achieved
        assert complete is False

    def test_check_kill_chain_progress_full(self) -> None:
        engine = self._make_engine()
        engine.award("red", "recon_complete", "Scan", 1)
        engine.award("red", "service_exploited", "SSH", 2)
        engine.award("red", "privesc_achieved", "SUID", 3)
        engine.award("red", "persistence_installed", "Backdoor", 4)
        achieved, complete = engine.check_kill_chain_progress()
        assert complete is True
        assert len(achieved) == 4


# ---------------------------------------------------------------------------
# Narrative tests
# ---------------------------------------------------------------------------


class TestNarrative:
    """Test narrative generation."""

    def test_generate_narrative_non_empty(self) -> None:
        narrative = generate_narrative(
            score_events=[],
            final_scores={"red": 10, "blue": 20},
            win_reason="Battle time expired",
            game_duration_seconds=300.0,
        )
        assert isinstance(narrative, str)
        assert len(narrative) > 0
        assert "GAME NARRATIVE" in narrative

    def test_narrative_contains_scores(self) -> None:
        narrative = generate_narrative(
            score_events=[],
            final_scores={"red": 45, "blue": 30},
            win_reason="Red completed full kill chain",
            game_duration_seconds=600.0,
        )
        assert "45" in narrative
        assert "30" in narrative
        assert "Red Team" in narrative

    def test_narrative_with_events(self) -> None:
        events = [
            {
                "agent_role": "red",
                "event_type": "recon_complete",
                "points": 5,
                "description": "Port scan done",
                "turn_number": 1,
            },
            {
                "agent_role": "blue",
                "event_type": "vuln_patched",
                "points": 10,
                "description": "SSH hardened",
                "turn_number": 2,
            },
        ]
        narrative = generate_narrative(
            score_events=events,
            final_scores={"red": 5, "blue": 10},
            win_reason="Battle time expired",
            game_duration_seconds=120.0,
        )
        assert "Port scan done" in narrative
        assert "SSH hardened" in narrative

    def test_narrative_winner_determination(self) -> None:
        narrative = generate_narrative(
            score_events=[],
            final_scores={"red": 0, "blue": 50},
            win_reason="Blue lockout",
            game_duration_seconds=60.0,
        )
        assert "Blue Team" in narrative
