"""Unit tests for skill registry and base_agent parse helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from skills.registry import SKILL_REGISTRY, get_skills_for_role, execute_skill
from agents.base_agent import _parse_skill_call


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestSkillRegistry:
    """Verify the global skill registry is populated correctly."""

    def test_total_skill_count(self) -> None:
        assert len(SKILL_REGISTRY) == 18, (
            f"Expected 18 skills, got {len(SKILL_REGISTRY)}: {list(SKILL_REGISTRY.keys())}"
        )

    def test_red_skills_count(self) -> None:
        red = [s for s in SKILL_REGISTRY.values() if s["role"] == "red"]
        assert len(red) == 8

    def test_blue_skills_count(self) -> None:
        blue = [s for s in SKILL_REGISTRY.values() if s["role"] == "blue"]
        assert len(blue) == 10

    def test_get_skills_for_role_red(self) -> None:
        red_skills = get_skills_for_role("red")
        assert len(red_skills) == 8
        names = {s["name"] for s in red_skills}
        assert "port_scan" in names
        assert "ssh_brute" in names

    def test_get_skills_for_role_blue(self) -> None:
        blue_skills = get_skills_for_role("blue")
        assert len(blue_skills) == 10
        names = {s["name"] for s in blue_skills}
        assert "block_ip" in names
        assert "harden_ssh" in names

    def test_get_skills_for_unknown_role(self) -> None:
        assert get_skills_for_role("purple") == []

    def test_skill_metadata_keys(self) -> None:
        """Each skill in get_skills_for_role output has name, description, parameters."""
        for skill in get_skills_for_role("red"):
            assert "name" in skill
            assert "description" in skill
            assert "parameters" in skill

    def test_execute_unknown_skill(self) -> None:
        result = execute_skill("nonexistent_skill", {}, "http://fake:8000")
        assert result["success"] is False
        assert "unknown skill" in result["error"]

    @patch("skills.red.recon.requests.post")
    def test_execute_port_scan_mock(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "exit_code": 0,
                "stdout": "22/tcp open ssh\n80/tcp open http",
                "stderr": "",
            }),
        )
        result = execute_skill("port_scan", {"target": "10.0.0.5"}, "http://fake:8000")
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# _parse_skill_call tests
# ---------------------------------------------------------------------------


class TestParseSkillCall:
    """Test the multi-layer skill call parser from base_agent."""

    def test_valid_json(self) -> None:
        text = '{"name": "port_scan", "parameters": {"target": "10.0.0.5"}, "reasoning": "recon"}'
        result = _parse_skill_call(text)
        assert result is not None
        assert result["name"] == "port_scan"
        assert result["parameters"]["target"] == "10.0.0.5"
        assert result["reasoning"] == "recon"

    def test_mixed_text_and_json(self) -> None:
        text = 'I will scan the target.\n{"name": "port_scan", "parameters": {"target": "10.0.0.5"}}'
        result = _parse_skill_call(text)
        assert result is not None
        assert result["name"] == "port_scan"

    def test_garbage_input(self) -> None:
        result = _parse_skill_call("this is not json at all")
        assert result is None

    def test_empty_string(self) -> None:
        result = _parse_skill_call("")
        assert result is None

    def test_json_without_name(self) -> None:
        result = _parse_skill_call('{"parameters": {"target": "10.0.0.5"}}')
        assert result is None

    def test_partial_json_with_name_field(self) -> None:
        text = 'Some text "name": "ssh_brute" and "parameters": {"target": "10.0.0.5"}'
        result = _parse_skill_call(text)
        assert result is not None
        assert result["name"] == "ssh_brute"

    def test_json_with_no_parameters(self) -> None:
        text = '{"name": "find_suid"}'
        result = _parse_skill_call(text)
        assert result is not None
        assert result["name"] == "find_suid"
        assert result["parameters"] == {}
