"""CyberSec Orchestrator — FastAPI app that filters, executes, and logs commands."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from orchestrator.db import (
    get_recent_decisions,
    init_db,
    log_decision,
    log_finding,
    log_safety_check,
)
from orchestrator.safety_filter import validate_command
from orchestrator.ssh_executor import CommandResult, execute_command

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
# Endpoints
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
