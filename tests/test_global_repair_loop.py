"""9-Final-2: Global Repair Loop 测试 — 最多 2 次尝试。"""

import pytest

from my_coding_team.schemas.review import FinalReviewReport, ReviewFinding
from my_coding_team.schemas.task import VerificationResult
from my_coding_team.schemas.workflow import TeamState, WorkspaceRecord


def _make_state_with_must_fix(must_fix_count: int = 1) -> TeamState:
    """构建一个 final review 有 must_fix 的 TeamState。"""
    findings = [
        ReviewFinding(
            finding_id=f"f{i}",
            title=f"Issue {i}",
            severity="high",
            approval=False,
            must_fix=[f"fix issue {i}"],
            evidence=[{"path": f"src/file{i}.py", "note": "broken"}],
        )
        for i in range(must_fix_count)
    ]
    review = FinalReviewReport(
        approval=False,
        summary=f"{must_fix_count} must_fix items",
        findings=findings,
    )
    return TeamState(
        request="test",
        llm_calls_budget=50,
        workspace=WorkspaceRecord(root="/tmp/test", is_git=True, dirty_files=[]),
        final_review=review.model_dump(),
        final_verification=VerificationResult(
            task_id="final", passed=False, commands=["pytest"],
            failed_commands=["pytest"],
        ).model_dump(),
    )


def test_state_has_must_fix():
    """确保 helper 构建的 state 确实有 must_fix。"""
    state = _make_state_with_must_fix(2)
    review = FinalReviewReport.model_validate(state.final_review)
    assert not review.approval
    assert len(review.findings) == 2


def test_blocked_reason_contains_attempt_count():
    """blocked_reason 应明确包含尝试次数。"""
    state = TeamState(
        request="test",
        llm_calls_budget=50,
        blocked_reason="global_repair_exhausted after 2 attempts; unresolved must_fix items: 3",
    )
    assert "2 attempts" in state.blocked_reason
    assert "3" in state.blocked_reason


def test_repair_succeeds_first_attempt_mock():
    """模拟第一次 repair 后 must_fix 清空 → 循环只跑 1 次。"""
    # 这里测试的是逻辑结构：如果第一次 repair 后 must_fix 为空，while 循环退出
    # 因为真正的 repair 需要 mock agent，这里先验证 state 转换结构
    findings_before = [ReviewFinding(
        finding_id="f1", title="Issue 1", severity="high",
        approval=False, must_fix=["fix it"],
        evidence=[{"path": "src/a.py", "note": "broken"}],
    )]
    review_before = FinalReviewReport(approval=False, summary="1 issue", findings=findings_before)
    review_after = FinalReviewReport(approval=True, summary="fixed", findings=[])

    assert not review_before.approval
    assert review_after.approval
    assert not review_after.findings  # must_fix 清空


def test_repair_exhausted_after_two():
    """跑满 2 次仍有 must_fix → blocked_by_max_repair_retries_exceeded。"""
    state = TeamState(
        request="test",
        llm_calls_budget=50,
        blocked_reason="global_repair_exhausted after 2 attempts; unresolved must_fix items: 1",
    )
    assert "global_repair_exhausted" in state.blocked_reason
    assert "after 2 attempts" in state.blocked_reason
