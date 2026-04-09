"""Generate a story-format narrative summary of a completed game."""

from __future__ import annotations


def generate_narrative(
    score_events: list[dict],
    final_scores: dict[str, int],
    win_reason: str,
    game_duration_seconds: float,
) -> str:
    """Produce a human-readable story of the game.

    Sections: opening, key moments, kill chain progress,
    final scores, stealth/detection summary, reasoning highlights.
    """
    lines: list[str] = []

    # -- Opening --
    minutes = int(game_duration_seconds // 60)
    seconds = int(game_duration_seconds % 60)
    red_score = final_scores.get("red", 0)
    blue_score = final_scores.get("blue", 0)
    winner = "Red Team" if red_score > blue_score else "Blue Team" if blue_score > red_score else "Neither team"

    lines.append("=" * 60)
    lines.append("GAME NARRATIVE SUMMARY")
    lines.append("=" * 60)
    lines.append("")
    lines.append(
        f"After {minutes}m {seconds}s of battle, {winner} emerged victorious."
    )
    lines.append(f"Outcome: {win_reason}")
    lines.append("")

    # -- Key Moments --
    lines.append("--- KEY MOMENTS ---")
    if not score_events:
        lines.append("  No scoring events recorded.")
    else:
        for evt in score_events:
            role = evt.get("agent_role", "?").upper()
            desc = evt.get("description", "")
            pts = evt.get("points", 0)
            turn = evt.get("turn_number", "?")
            lines.append(f"  [Turn {turn}] {role}: {desc} (+{pts} pts)")
    lines.append("")

    # -- Kill Chain Progress --
    red_chain_events = [
        e for e in score_events
        if e.get("agent_role") == "red"
        and e.get("event_type", "") in (
            "recon_complete", "service_exploited",
            "privesc_achieved", "persistence_installed", "full_kill_chain",
        )
    ]
    lines.append("--- KILL CHAIN PROGRESS ---")
    if red_chain_events:
        for evt in red_chain_events:
            lines.append(f"  {evt.get('event_type', '')}: {evt.get('description', '')}")
    else:
        lines.append("  Red team did not advance through the kill chain.")
    lines.append("")

    # -- Final Scores --
    lines.append("--- FINAL SCORES ---")
    lines.append(f"  Red Team:  {red_score} points")
    lines.append(f"  Blue Team: {blue_score} points")
    lines.append("")

    # -- Stealth / Detection --
    stealth_events = [
        e for e in score_events
        if e.get("event_type", "") in ("red_undetected_action", "blue_detected_stealthily")
    ]
    lines.append("--- STEALTH & DETECTION ---")
    if stealth_events:
        for evt in stealth_events:
            lines.append(
                f"  {evt.get('agent_role', '').upper()}: "
                f"{evt.get('description', '')} (+{evt.get('points', 0)} pts)"
            )
    else:
        lines.append("  No stealth or detection bonuses awarded.")
    lines.append("")

    # -- Reasoning Highlights --
    reasoning_types = {"pivot_on_failure", "correct_inference", "adaptive_escalation"}
    reasoning_events = [
        e for e in score_events if e.get("event_type", "") in reasoning_types
    ]
    lines.append("--- AI REASONING HIGHLIGHTS ---")
    if reasoning_events:
        for evt in reasoning_events:
            lines.append(
                f"  {evt.get('agent_role', '').upper()}: "
                f"{evt.get('description', '')} (+{evt.get('points', 0)} pts)"
            )
    else:
        lines.append("  No reasoning bonuses awarded this game.")
    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)
