"""Phase 9a Design Signoff 和 full product workflow 测试。"""

import pytest
from pathlib import Path

from my_coding_team.schemas.workflow import (
    DesignSignoff,
    ProblemFrame,
    ProductBrief,
    TeamState,
)
from my_coding_team.workflows.full_product import (
    _build_blocked_from_state,
    _build_success_delivery,
)


def test_problem_frame_rejects_recommended_not_in_candidates():
    """recommended_direction 不在 candidate_directions 中应抛 ValidationError。"""
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        ProblemFrame(
            user_request="x",
            problem="x",
            candidate_directions=["Option A", "Option B"],
            recommended_direction="Option C",
        )
    assert "recommended_direction must be one of candidate_directions" in str(exc_info.value)


def test_problem_frame_rejects_too_few_candidates():
    """candidate_directions 少于 2 应抛 ValidationError。"""
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        ProblemFrame(
            user_request="x",
            problem="x",
            candidate_directions=["Only one"],
            recommended_direction="Only one",
        )
    assert "candidate_directions must have 2-4 items" in str(exc_info.value)


def test_problem_frame_rejects_too_many_candidates():
    """candidate_directions 多于 4 应抛 ValidationError。"""
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        ProblemFrame(
            user_request="x",
            problem="x",
            candidate_directions=["A", "B", "C", "D", "E"],
            recommended_direction="A",
        )
    assert "candidate_directions must have 2-4 items" in str(exc_info.value)


def test_problem_frame_accepts_empty_candidates():
    """空的 candidate_directions 允许（未经过 Shape 的状态）。"""
    frame = ProblemFrame(user_request="x", problem="x")
    assert frame.candidate_directions == []
    assert frame.recommended_direction == ""


def test_build_blocked_from_state():
    """blocked state 应生成 blocked delivery。"""
    state = TeamState(
        request="Test",
        llm_calls_budget=10,
        blocked_reason="test_block",
        status="blocked",
    )
    pkg = _build_blocked_from_state(state)
    assert pkg.decision.status == "blocked"
    assert "test_block" in pkg.decision.reason


def test_build_success_delivery_no_tasks():
    """无任务结果时应生成空 success delivery。"""
    state = TeamState(request="Test", llm_calls_budget=10, status="success")
    pkg = _build_success_delivery(state)
    assert pkg.decision.status == "success"
    assert pkg.changed_files == []
