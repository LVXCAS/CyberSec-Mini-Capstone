"""Regression tests for act_node response parsing.

Verifies that act_node correctly parses the orchestrator ExecuteResponse schema:
  {allowed: bool, reason: str, blocked_command: str|null, result: {exit_code, stdout, stderr} | null}
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from agents.base_agent import act_node


def _make_state(command: str = "whoami") -> dict:
    """Return a minimal AgentState dict for act_node."""
    return {
        "agent_role": "red",
        "system_prompt": "You are a red agent.",
        "turn_number": 1,
        "max_turns": 10,
        "observations": [],
        "executed_commands": [],
        "findings": [],
        "messages": [{"role": "assistant", "content": json.dumps({
            "tool": "execute",
            "args": {"cmd": command},
            "reasoning": "test reasoning",
        })}],
        "done": False,
        "last_result": {},
    }


def _mock_response(payload: dict) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.json.return_value = payload
    return mock_resp


class TestActNodeParsing:
    """Regression tests for act_node orchestrator response parsing."""

    @patch("agents.base_agent._log_decision")
    @patch("agents.base_agent.requests.post")
    def test_allowed_command_with_output(self, mock_post, mock_log):
        """Allowed command: exit_code==0, stdout populated, finding appended."""
        mock_post.return_value = _mock_response({
            "allowed": True,
            "reason": "ok",
            "blocked_command": None,
            "result": {
                "exit_code": 0,
                "stdout": "flag found in /etc/passwd",
                "stderr": "",
            },
        })

        state = _make_state("cat /etc/passwd")
        result = act_node(state)

        assert result["last_result"]["exit_code"] == 0
        assert "flag" in result["last_result"]["stdout"]
        assert result["last_result"]["blocked"] is False
        assert len(result["findings"]) == 1
        assert result["findings"][0]["command"] == "cat /etc/passwd"

    @patch("agents.base_agent._log_decision")
    @patch("agents.base_agent.requests.post")
    def test_blocked_command(self, mock_post, mock_log):
        """Blocked command: was_blocked==True, exit_code==-1, stdout empty."""
        mock_post.return_value = _mock_response({
            "allowed": False,
            "reason": "dangerous command",
            "blocked_command": "rm -rf /",
            "result": None,
        })

        state = _make_state("rm -rf /")
        result = act_node(state)

        assert result["last_result"]["blocked"] is True
        assert result["last_result"]["exit_code"] == -1
        assert result["last_result"]["stdout"] == ""
        assert len(result["findings"]) == 0

    @patch("agents.base_agent._log_decision")
    @patch("agents.base_agent.requests.post")
    def test_allowed_command_nonzero_exit(self, mock_post, mock_log):
        """Allowed command with nonzero exit: no finding appended."""
        mock_post.return_value = _mock_response({
            "allowed": True,
            "reason": "ok",
            "blocked_command": None,
            "result": {
                "exit_code": 1,
                "stdout": "error msg: command failed",
                "stderr": "fail",
            },
        })

        state = _make_state("ls /nonexistent")
        result = act_node(state)

        assert result["last_result"]["exit_code"] == 1
        assert "error" in result["last_result"]["stdout"]
        assert result["last_result"]["blocked"] is False
        assert len(result["findings"]) == 0
