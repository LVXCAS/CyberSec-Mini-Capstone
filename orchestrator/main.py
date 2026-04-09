"""CyberSec Orchestrator — FastAPI app that filters, executes, logs commands, and manages game state."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from orchestrator.db import (
    get_recent_decisions,
    get_score_events,
    get_scores,
    init_db,
    log_decision,
    log_finding,
    log_safety_check,
    log_score_event,
    log_snapshot,
)
from orchestrator.safety_filter import validate_command
from orchestrator.ssh_executor import CommandResult, execute_command

from game.narrative import generate_narrative
from game.scoring import POINT_VALUES, ScoringEngine
from game.snapshots import SnapshotManager
from game.state import GameContext, GamePhase, advance_phase, check_win_condition

logger = logging.getLogger("orchestrator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ExecuteRequest(BaseModel):
    agent_role: str
    command: str
    reasoning: str = ""
    turn_number: int = 0


class ExecuteResponse(BaseModel):
    allowed: bool
    reason: Optional[str] = None
    blocked_command: Optional[str] = None
    result: Optional[CommandResult] = None


class FindingRequest(BaseModel):
    agent_role: str
    finding_type: str
    description: str
    severity: str
    raw_data: str = ""


class ScoreRequest(BaseModel):
    agent_role: str
    event_type: str
    description: str
    turn_number: int


class ScoreResponse(BaseModel):
    points_awarded: int
    total_scores: dict
    game_over: bool
    win_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Module-level game state (single-process demo)
# ---------------------------------------------------------------------------

_game_ctx: Optional[GameContext] = None
_scoring: Optional[ScoringEngine] = None
_snapshot_mgr: Optional[SnapshotManager] = None
_game_narrative: Optional[str] = None


# ---------------------------------------------------------------------------
# Lifespan — init DB + test SSH on startup
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialized")

    # Test SSH connection (non-fatal)
    try:
        probe = execute_command("echo ok", timeout=5)
        if probe.exit_code == 0:
            logger.info("SSH connection to battleground verified")
        else:
            logger.warning("SSH probe returned exit_code=%d: %s", probe.exit_code, probe.stderr)
    except Exception as exc:
        logger.warning("SSH probe failed (non-fatal): %s", exc)

    yield


app = FastAPI(title="CyberSec Orchestrator", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Existing endpoints (unchanged)
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/execute", response_model=ExecuteResponse)
async def execute(req: ExecuteRequest):
    # 1. Safety filter
    filter_result = validate_command(req.command, req.agent_role)

    # 2. Log safety check
    log_safety_check(
        agent_role=req.agent_role,
        command=req.command,
        allowed=filter_result.allowed,
        reason=filter_result.reason,
    )

    # 3. If blocked
    if not filter_result.allowed:
        log_decision(
            agent_role=req.agent_role,
            turn_number=req.turn_number,
            command=req.command,
            reasoning=req.reasoning,
            was_blocked=True,
            block_reason=filter_result.reason,
        )
        logger.warning(
            "BLOCKED command from %s: %s — %s",
            req.agent_role,
            req.command,
            filter_result.reason,
        )
        return ExecuteResponse(
            allowed=False,
            reason=filter_result.reason,
            blocked_command=req.command,
        )

    # 4. Execute via SSH
    result = execute_command(filter_result.sanitized_command or req.command)

    # 5. Log decision
    log_decision(
        agent_role=req.agent_role,
        turn_number=req.turn_number,
        command=req.command,
        reasoning=req.reasoning,
        result_stdout=result.stdout,
        result_stderr=result.stderr,
        exit_code=result.exit_code,
    )

    logger.info(
        "EXECUTED for %s: %s (exit=%d, %dms)",
        req.agent_role,
        req.command,
        result.exit_code,
        result.execution_time_ms,
    )
    return ExecuteResponse(allowed=True, result=result)


@app.get("/decisions/{agent_role}")
async def decisions(agent_role: str, n: int = 10):
    return get_recent_decisions(agent_role, n)


@app.post("/findings")
async def findings(req: FindingRequest):
    log_finding(
        agent_role=req.agent_role,
        finding_type=req.finding_type,
        description=req.description,
        severity=req.severity,
        raw_data=req.raw_data,
    )
    return {"status": "logged"}


# ---------------------------------------------------------------------------
# Game control endpoints
# ---------------------------------------------------------------------------


@app.post("/game/start")
async def game_start():
    """Start a new game session."""
    global _game_ctx, _scoring, _snapshot_mgr, _game_narrative

    _game_ctx = GameContext(
        phase=GamePhase.SETUP,
        start_time=time.monotonic(),
    )
    _scoring = ScoringEngine(db_log_fn=log_score_event)
    _snapshot_mgr = SnapshotManager(
        interval=60,
        orchestrator_url="http://localhost:8000",
        db_log_fn=log_snapshot,
    )
    _snapshot_mgr.start()
    _game_narrative = None

    logger.info("Game started — phase=setup")
    return {
        "status": "started",
        "phase": "setup",
        "setup_duration": _game_ctx.setup_duration,
        "battle_duration": _game_ctx.battle_duration,
    }


@app.post("/game/advance")
async def game_advance():
    """Advance the game to the next phase."""
    global _game_ctx, _game_narrative

    if _game_ctx is None:
        raise HTTPException(status_code=400, detail="Game not started")

    old_phase = _game_ctx.phase
    _game_ctx = advance_phase(_game_ctx)
    new_phase = _game_ctx.phase

    logger.info("Game phase advanced: %s -> %s", old_phase.value, new_phase.value)

    if new_phase == GamePhase.CONCLUSION:
        # Stop snapshots and generate narrative
        if _snapshot_mgr is not None:
            _snapshot_mgr.stop()
        if _scoring is not None:
            events = get_score_events()
            scores = _scoring.get_totals()
            elapsed = time.monotonic() - _game_ctx.start_time if _game_ctx.start_time > 0 else 0
            _, win_reason = check_win_condition(_game_ctx, scores)
            _game_narrative = generate_narrative(
                events, scores, win_reason or "Game concluded", elapsed,
            )

    return {"phase": new_phase.value}


@app.get("/game/status")
async def game_status():
    """Get current game state including scores and win condition."""
    if _game_ctx is None:
        return {
            "phase": "not_started",
            "elapsed": 0,
            "scores": {"red": 0, "blue": 0},
            "red_kill_chain": [],
            "win_condition": {"game_over": False, "reason": ""},
        }

    scores = _scoring.get_totals() if _scoring else {"red": 0, "blue": 0}
    elapsed = time.monotonic() - _game_ctx.start_time if _game_ctx.start_time > 0 else 0
    game_over, reason = check_win_condition(_game_ctx, scores)

    return {
        "phase": _game_ctx.phase.value,
        "elapsed": round(elapsed, 1),
        "scores": scores,
        "red_kill_chain": list(_game_ctx.red_kill_chain),
        "win_condition": {"game_over": game_over, "reason": reason},
    }


@app.post("/game/score", response_model=ScoreResponse)
async def game_score(req: ScoreRequest):
    """Award points for a game event."""
    if _scoring is None:
        raise HTTPException(status_code=400, detail="Game not started")

    points = _scoring.award(
        agent_role=req.agent_role,
        event_type=req.event_type,
        description=req.description,
        turn_number=req.turn_number,
    )

    scores = _scoring.get_totals()
    game_over = False
    win_reason: Optional[str] = None
    if _game_ctx is not None:
        game_over, win_reason_str = check_win_condition(_game_ctx, scores)
        win_reason = win_reason_str or None

    return ScoreResponse(
        points_awarded=points,
        total_scores=scores,
        game_over=game_over,
        win_reason=win_reason,
    )


@app.get("/game/narrative")
async def game_narrative():
    """Get the final game narrative (only available after conclusion)."""
    if _game_ctx is None or _game_ctx.phase != GamePhase.CONCLUSION:
        raise HTTPException(
            status_code=400,
            detail="Narrative only available after game conclusion",
        )
    return {"narrative": _game_narrative or "No narrative generated."}
