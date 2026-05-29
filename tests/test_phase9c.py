"""Phase 9c Branch Finisher 和 Final Review/Verification 测试。"""

import pytest

from my_coding_team.agents import qa_verification as _qa_verification  # noqa: F401
from my_coding_team.rooms import review_room as _review_room  # noqa: F401
from my_coding_team.core.registry import ROOMS, STEPS
from my_coding_team.core.step import StepContext
from my_coding_team.orchestration.branch_finisher import BranchFinishDecision, decide_branch_finish
from my_coding_team.schemas.room_inputs import ReviewRoomInput
from my_coding_team.schemas.step_inputs import QAVerificationInput
from my_coding_team.schemas.review import FinalReviewReport, ReviewFinding
from my_coding_team.schemas.task import ImplementationResult, TaskRunResult, VerificationResult
from my_coding_team.schemas.workflow import ProductBrief, WorkspaceRecord


# ── Branch Finisher ──

def test_branch_finisher_open_pr_on_clean_git():
    """干净的 Git 仓库 + 全部通过 → 建议提 PR。"""
    ws = WorkspaceRecord(root="/tmp/repo", is_git=True, dirty_files=[])
    ver = VerificationResult(task_id="final", passed=True, commands=["pytest"])
    review = FinalReviewReport(approval=True, summary="all good")
    decision = decide_branch_finish(ws, ver, review)
    assert decision.action == "open_pr"


def test_branch_finisher_keep_on_verification_failure():
    """验证失败 → 保留工作区。"""
    ws = WorkspaceRecord(root="/tmp/repo", is_git=True, dirty_files=[])
    ver = VerificationResult(task_id="final", passed=False, commands=["pytest"], failed_commands=["pytest"])
    review = FinalReviewReport(approval=True, summary="tests failed")
    decision = decide_branch_finish(ws, ver, review)
    assert decision.action == "keep_worktree_for_follow_up"


def test_branch_finisher_keep_on_review_must_fix():
    """Review 有 must_fix → 保留分支。"""
    ws = WorkspaceRecord(root="/tmp/repo", is_git=True, dirty_files=[])
    ver = VerificationResult(task_id="final", passed=True, commands=["pytest"])
    review = FinalReviewReport(
        approval=False,
        summary="issues found",
        findings=[
            ReviewFinding(
                finding_id="f1", title="Bug", severity="high",
                approval=False, must_fix=["fix bug"],
                evidence=[{"path": "src/a.py", "note": "broken"}],
            ),
        ],
    )
    decision = decide_branch_finish(ws, ver, review)
    assert decision.action == "keep_branch_for_user_review"


def test_branch_finisher_dirty_worktree():
    """dirty worktree → 保留让用户处理。"""
    ws = WorkspaceRecord(root="/tmp/repo", is_git=True, dirty_files=["README.md"])
    ver = VerificationResult(task_id="final", passed=True, commands=["pytest"])
    review = FinalReviewReport(approval=True, summary="good but dirty")
    decision = decide_branch_finish(ws, ver, review)
    assert decision.action == "keep_worktree_for_follow_up"


def test_branch_finisher_non_git():
    """非 Git 仓库 → 只报告。"""
    ws = WorkspaceRecord(root="/tmp/non_git", is_git=False, dirty_files=[])
    ver = VerificationResult(task_id="final", passed=True, commands=["pytest"])
    review = FinalReviewReport(approval=True, summary="ok")
    decision = decide_branch_finish(ws, ver, review)
    assert decision.action == "report_only"


# ── QA Verification scope=final ──

@pytest.mark.asyncio
async def test_qa_verification_final_scope():
    """scope=final 应该接受 commands 参数。"""
    ver = await STEPS["qa_verification"].run(
        QAVerificationInput(scope="final", commands=["python -m pytest"]),
        StepContext(),
    )
    assert ver.task_id == "final"
    assert isinstance(ver, VerificationResult)


@pytest.mark.asyncio
async def test_qa_verification_final_no_commands():
    """scope=final 没有 commands → 返回 passed=False。"""
    ver = await STEPS["qa_verification"].run(
        QAVerificationInput(scope="final", commands=[]),
        StepContext(),
    )
    assert not ver.passed


# ── ReviewRoom scope=final ──

@pytest.mark.asyncio
async def test_review_room_final_no_tasks():
    """scope=final 无任务结果时应返回 FinalReviewReport。"""
    result = await ROOMS["review_room"].execute(
        ReviewRoomInput(scope="final", brief=None, task_results=None, final_verification=None),
        StepContext(),
    )
    assert isinstance(result, FinalReviewReport)


@pytest.mark.asyncio
async def test_review_room_final_with_blocked_task():
    """scope=final 有 blocked 任务时应上报告 must_fix。"""
    tr = TaskRunResult(
        task_id="T1",
        status="blocked_must_fix",
        implementation=ImplementationResult(task_id="T1", success=False, summary="blocked"),
        verification=VerificationResult(task_id="T1", passed=False),
    )
    result = await ROOMS["review_room"].execute(
        ReviewRoomInput(scope="final", brief=None, task_results=[tr.model_dump()], final_verification=None),
        StepContext(),
    )
    assert isinstance(result, FinalReviewReport)
    assert not result.approval


@pytest.mark.asyncio
async def test_review_room_final_all_passed():
    """scope=final 全部通过 → approval=True。"""
    tr = TaskRunResult(
        task_id="T1",
        status="completed",
        implementation=ImplementationResult(task_id="T1", success=True, summary="done"),
        verification=VerificationResult(task_id="T1", passed=True, commands=["pytest"]),
    )
    final_ver = VerificationResult(task_id="final", passed=True, commands=["pytest"])
    result = await ROOMS["review_room"].execute(
        ReviewRoomInput(
            scope="final",
            brief=None,
            task_results=[tr.model_dump()],
            final_verification=final_ver.model_dump(),
        ),
        StepContext(),
    )
    assert isinstance(result, FinalReviewReport)
    assert result.approval
