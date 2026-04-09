"""Game loop: orchestrates blue setup, alternating battle, and conclusion phases.

Calls orchestrator HTTP endpoints to advance game state and coordinates
both agents (red and blue) sequentially through a single KoboldCpp instance.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from skills.registry import SKILL_REGISTRY

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

_RED_SCORE_MAP: dict[str, dict[str, str]] = {
    "port_scan": {"keyword": "open", "event": "recon_complete"},
    "ssh_brute": {"keyword": "success", "event": "service_exploited"},
    "find_suid": {"keyword": "exploitable", "event": "privesc_achieved"},
    "web_sql_inject": {"keyword": "success", "event": "service_exploited"},
    "install_backdoor": {"keyword": "success", "event": "persistence_installed"},
    "create_persistence": {"keyword": "success", "event": "persistence_installed"},
    "exfil_data": {"keyword": "success", "event": "persistence_installed"},
    "web_dir_enum": {"keyword": "found", "event": "recon_complete"},
}

_BLUE_SCORE_MAP: dict[str, dict[str, str]] = {
    "harden_ssh": {"keyword": "success", "event": "vuln_patched"},
    "configure_firewall": {"keyword": "success", "event": "vuln_patched"},
    "block_ip": {"keyword": "success", "event": "attacker_blocked"},
    "detect_intrusion": {"keyword": "detected", "event": "attack_detected"},
    "check_auth_logs": {"keyword": "found", "event": "attack_detected"},
    "scan_processes": {"keyword": "running", "event": "service_kept_up"},
    "check_file_integrity": {"keyword": "success", "event": "attack_detected"},
    "kill_process": {"keyword": "success", "event": "attacker_blocked"},
    "remove_backdoor": {"keyword": "success", "event": "attacker_blocked"},
    "check_suid": {"keyword": "success", "event": "vuln_patched"},
}


def score_red_action(
    last_skill: str,
    last_result: dict,
    turn_number: int,
    orchestrator_url: str,
) -> None:
    """Score a red agent action via the orchestrator scoring endpoint."""
    mapping = _RED_SCORE_MAP.get(last_skill)
    if mapping is None:
        return

    result_str = str(last_result).lower()
    if mapping["keyword"] in result_str:
        _post_score_event(
            orchestrator_url,
            agent_role="red",
            event_type=mapping["event"],
            description=f"{last_skill} succeeded",
            turn_number=turn_number,
        )


def score_blue_action(
    last_skill: str,
    last_result: dict,
    turn_number: int,
    orchestrator_url: str,
) -> None:
    """Score a blue agent action via the orchestrator scoring endpoint."""
    mapping = _BLUE_SCORE_MAP.get(last_skill)
    if mapping is None:
        return

    result_str = str(last_result).lower()
    if mapping["keyword"] in result_str:
        _post_score_event(
            orchestrator_url,
            agent_role="blue",
            event_type=mapping["event"],
            description=f"{last_skill} succeeded",
            turn_number=turn_number,
        )


def _post_score_event(
    orchestrator_url: str,
    agent_role: str,
    event_type: str,
    description: str,
    turn_number: int,
) -> None:
    """POST a score event to the orchestrator."""
    try:
        requests.post(
            f"{orchestrator_url}/game/score",
            json={
                "agent_role": agent_role,
                "event_type": event_type,
                "description": description,
                "turn_number": turn_number,
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.warning("Failed to post score event: %s", exc)


# ---------------------------------------------------------------------------
# Agent turn runner
# ---------------------------------------------------------------------------


def _run_agent_turn(
    role: str,
    orchestrator_url: str,
    game_phase: str,
    current_turn: int,
) -> dict:
    """Run a single agent turn by calling the orchestrator agent endpoint.

    Returns the agent state dict after one turn.
    """
    from agents.base_agent import run_agent
    from skills.registry import SKILL_REGISTRY

    # Filter skills by role
    role_skills = [
        {"name": name, "description": meta.get("description", "")}
        for name, meta in SKILL_REGISTRY.items()
        if meta.get("role") == role
    ]

    system_prompts = {
        "red": (
            "You are an autonomous red team agent. Your goal is to gain access "
            "to the target system, escalate privileges, and establish persistence. "
            "Think step by step about reconnaissance, exploitation, and post-exploitation."
        ),
        "blue": (
            "You are an autonomous blue team agent. Your goal is to harden the system, "
            "detect intrusions, and block attackers. During setup phase, focus on "
            "hardening. During battle, focus on detection and response."
        ),
    }

    state = run_agent(
        role=role,
        system_prompt=system_prompts.get(role, system_prompts["blue"]),
        max_turns=current_turn + 1,  # Run exactly 1 turn from current position
        available_skills=role_skills,
        game_phase=game_phase,
    )

    return state


# ---------------------------------------------------------------------------
# Main game loop
# ---------------------------------------------------------------------------


def run_game(
    orchestrator_url: str = "http://localhost:8000",
    setup_minutes: int = 5,
    battle_minutes: int = 20,
    max_turns_per_agent: int = 30,
) -> dict:
    """Run the full game lifecycle: setup -> battle -> conclusion.

    Args:
        orchestrator_url: Base URL for the orchestrator API.
        setup_minutes: Duration of the blue setup phase in minutes.
        battle_minutes: Duration of the battle phase in minutes.
        max_turns_per_agent: Maximum turns each agent gets in battle.

    Returns:
        Result dict with final scores, narrative, and game outcome.
    """
    setup_seconds = setup_minutes * 60
    battle_seconds = battle_minutes * 60
    max_setup_turns = 8

    # ------------------------------------------------------------------
    # 1. Initialize
    # ------------------------------------------------------------------
    logger.info("Game starting.")
    try:
        requests.post(f"{orchestrator_url}/game/start", timeout=10)
    except requests.RequestException as exc:
        logger.error("Failed to start game: %s", exc)
        return {"error": str(exc)}

    # ------------------------------------------------------------------
    # 2. Setup phase (blue only)
    # ------------------------------------------------------------------
    logger.info("Setup phase: blue agent hardening (%d turns max).", max_setup_turns)
    setup_start = time.monotonic()

    for turn in range(max_setup_turns):
        elapsed = time.monotonic() - setup_start
        if elapsed >= setup_seconds:
            logger.info("Setup time expired at turn %d.", turn)
            break

        state = _run_agent_turn(
            role="blue",
            orchestrator_url=orchestrator_url,
            game_phase="setup",
            current_turn=turn,
        )

        last_result = state.get("last_result", {})
        last_skill = ""
        if state.get("findings"):
            last_skill = state["findings"][-1].get("skill", "")

        score_blue_action(last_skill, last_result, turn, orchestrator_url)
        logger.info("Setup turn %d complete. Skill: %s", turn, last_skill)

    # Advance to battle
    try:
        requests.post(f"{orchestrator_url}/game/advance", timeout=10)
    except requests.RequestException as exc:
        logger.warning("Failed to advance to battle: %s", exc)

    # ------------------------------------------------------------------
    # 3. Battle phase (alternating turns)
    # ------------------------------------------------------------------
    logger.info("Battle phase: alternating red/blue turns.")
    battle_start = time.monotonic()
    last_red_action_turn: int = -10  # Track for stealth bonus
    last_blue_detect_turn: int = -10

    for turn in range(max_turns_per_agent):
        elapsed = time.monotonic() - battle_start
        if elapsed >= battle_seconds:
            logger.info("Battle time expired at turn %d.", turn)
            break

        # --- Red turn ---
        red_state = _run_agent_turn(
            role="red",
            orchestrator_url=orchestrator_url,
            game_phase="battle",
            current_turn=turn,
        )

        red_skill = ""
        if red_state.get("findings"):
            red_skill = red_state["findings"][-1].get("skill", "")

        score_red_action(
            red_skill, red_state.get("last_result", {}), turn, orchestrator_url
        )
        last_red_action_turn = turn

        # Check win condition
        if _check_game_over(orchestrator_url):
            break

        # --- Blue turn ---
        blue_state = _run_agent_turn(
            role="blue",
            orchestrator_url=orchestrator_url,
            game_phase="battle",
            current_turn=turn,
        )

        blue_skill = ""
        if blue_state.get("findings"):
            blue_skill = blue_state["findings"][-1].get("skill", "")

        score_blue_action(
            blue_skill, blue_state.get("last_result", {}), turn, orchestrator_url
        )

        # Stealth bonus: if red acted and blue didn't detect within 2 turns
        blue_detected = blue_skill in (
            "detect_intrusion",
            "check_auth_logs",
            "check_file_integrity",
        )
        if blue_detected:
            last_blue_detect_turn = turn

        if (
            turn - last_red_action_turn <= 2
            and last_blue_detect_turn < last_red_action_turn
        ):
            _post_score_event(
                orchestrator_url,
                agent_role="red",
                event_type="red_undetected_action",
                description="Red action undetected within stealth window",
                turn_number=turn,
            )

        # Check win condition
        if _check_game_over(orchestrator_url):
            break

        logger.info(
            "Battle turn %d complete. Red: %s, Blue: %s", turn, red_skill, blue_skill
        )

    # ------------------------------------------------------------------
    # 4. Conclusion
    # ------------------------------------------------------------------
    logger.info("Advancing to conclusion.")
    try:
        requests.post(f"{orchestrator_url}/game/advance", timeout=10)
    except requests.RequestException as exc:
        logger.warning("Failed to advance to conclusion: %s", exc)

    # Fetch final results
    result: dict[str, Any] = {"status": "completed"}

    try:
        status_resp = requests.get(f"{orchestrator_url}/game/status", timeout=10)
        if status_resp.status_code == 200:
            result["game_status"] = status_resp.json()
    except requests.RequestException:
        pass

    try:
        narrative_resp = requests.get(f"{orchestrator_url}/game/narrative", timeout=10)
        if narrative_resp.status_code == 200:
            result["narrative"] = narrative_resp.json()
    except requests.RequestException:
        pass

    logger.info("Game complete. Result: %s", result.get("game_status", {}))
    return result


def _check_game_over(orchestrator_url: str) -> bool:
    """Check if the game has ended via orchestrator status."""
    try:
        resp = requests.get(f"{orchestrator_url}/game/status", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            phase = data.get("phase", "")
            if phase == "conclusion":
                return True
    except requests.RequestException:
        pass
    return False
