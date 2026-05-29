"""9-Final-1: Signoff CLI 交互测试。"""

import io
from unittest.mock import patch

import pytest

from my_coding_team.orchestration.signoff import request_design_signoff_cli
from my_coding_team.schemas.workflow import ProductBrief


def _make_brief() -> ProductBrief:
    """构建测试用 ProductBrief。"""
    return ProductBrief(
        title="Test Feature",
        summary="A test feature for signoff.",
        goals=["Goal 1"],
        non_goals=["Not doing X", "Not doing Y"],
        requirements=["Req 1"],
        acceptance_criteria=["pytest passes"],
        assumptions=["assume 1"],
        open_questions=["question 1"],
    )


def test_approve_yes():
    """Y 输入 → approve as-is，open_questions 不转为 assumptions。"""
    with patch("sys.stdin", io.StringIO("y\n")), patch("sys.stdin.isatty", return_value=True):
        result = request_design_signoff_cli(_make_brief())
    assert result.permission_to_plan is True
    assert result.reason == "user_approved"
    assert "question 1" not in result.accepted_assumptions
    assert "assume 1" in result.accepted_assumptions


def test_approve_with_assumptions():
    """A 输入 → approve，open_questions 转为 assumptions。"""
    with patch("sys.stdin", io.StringIO("a\n")), patch("sys.stdin.isatty", return_value=True):
        result = request_design_signoff_cli(_make_brief())
    assert result.permission_to_plan is True
    assert "question 1" in result.accepted_assumptions
    assert "assume 1" in result.accepted_assumptions
    assert result.reason == "user_approved_with_questions_as_assumptions"


def test_reject():
    """N 输入 → reject。"""
    with patch("sys.stdin", io.StringIO("n\nout of scope\n")), patch("sys.stdin.isatty", return_value=True):
        result = request_design_signoff_cli(_make_brief())
    assert result.permission_to_plan is False
    assert result.reason == "out of scope"


def test_invalid_then_approve():
    """非法输入后重新输入有效选择。"""
    with patch("sys.stdin", io.StringIO("maybe\ny\n")), patch("sys.stdin.isatty", return_value=True):
        result = request_design_signoff_cli(_make_brief())
    assert result.permission_to_plan is True


def test_non_interactive_auto_approve():
    """无 tty → auto-approve，不破坏 CI/测试。"""
    with patch("sys.stdin.isatty", return_value=False):
        result = request_design_signoff_cli(_make_brief())
    assert result.permission_to_plan is True
    assert result.reason == "auto_approved_non_interactive"


def test_stdin_eof_auto_approve():
    """TTY-like runners without readable stdin should use the non-interactive fallback."""
    with patch("sys.stdin", io.StringIO("")), patch("sys.stdin.isatty", return_value=True):
        result = request_design_signoff_cli(_make_brief())
    assert result.permission_to_plan is True
    assert result.reason == "auto_approved_non_interactive"


def test_simulated_yes_from_env():
    """Smoke runners can force a Y decision without relying on terminal stdin."""
    with patch.dict("os.environ", {"MY_CODING_TEAM_SIGNOFF_CHOICE": "y"}, clear=False):
        result = request_design_signoff_cli(_make_brief())
    assert result.permission_to_plan is True
    assert result.reason == "user_approved"


def test_simulated_no_from_env():
    """Smoke runners can force an N decision and validate the signoff gate."""
    with patch.dict(
        "os.environ",
        {
            "MY_CODING_TEAM_SIGNOFF_CHOICE": "n",
            "MY_CODING_TEAM_SIGNOFF_REASON": "smoke_rejected",
        },
        clear=False,
    ):
        result = request_design_signoff_cli(_make_brief())
    assert result.permission_to_plan is False
    assert result.reason == "smoke_rejected"
