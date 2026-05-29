"""Delivery package construction."""

from __future__ import annotations

from my_coding_team.schemas.delivery import DeliveryPackage, FinishDecision
from my_coding_team.schemas.review import FinalReviewReport, ReviewOnlyReport, TaskReviewResult
from my_coding_team.schemas.task import VerificationResult
from my_coding_team.schemas.workflow import TeamState


def build_delivery_package(
    state: TeamState,
    *,
    status: str = "success",
    reason: str = "completed",
    summary: str = "",
    changed_files: list[str] | None = None,
    verification: list[VerificationResult] | None = None,
    review: TaskReviewResult | FinalReviewReport | ReviewOnlyReport | None = None,
    risks: list[str] | None = None,
) -> DeliveryPackage:
    """构建最终交付包，统一描述结果、验证、审查和风险。

    参数：
        state: 当前 TeamState。
        status: 交付状态，取 success、blocked 或 failed。
        reason: 状态原因，供 CLI 和文档展示。
        summary: 面向用户的结果摘要。
        changed_files: 本次修改的相对文件路径。
        verification: QA Verification 结果列表。
        review: TaskReviewResult 或 FinalReviewReport。
        risks: 剩余风险说明。

    返回：
        可序列化的 DeliveryPackage。
    """
    final_review = None
    if isinstance(review, FinalReviewReport):
        final_review = review
    elif isinstance(review, TaskReviewResult):
        final_review = FinalReviewReport(
            approval=review.approval,
            summary=review.summary,
            findings=review.findings,
        )
    elif isinstance(review, ReviewOnlyReport):
        final_review = FinalReviewReport(
            approval=review.finding.approval,
            summary=review.finding.title,
            findings=[review.finding],
            residual_risks=[*review.should_fix, *review.nice_to_have],
        )
    return DeliveryPackage(
        request=state.request,
        decision=FinishDecision(status=status, reason=reason),
        summary=summary,
        changed_files=changed_files or [],
        verification=verification or [],
        review=final_review,
        risks=risks or [],
        llm_calls_used=state.llm_calls_used,
        workflow_kind=state.workflow,
        red_results=state.red_results,
        pm_overrides=state.pm_overrides,
        diagnostics={
            "current_phase": state.current_phase,
            "blocked_reason": state.blocked_reason,
            "task_queue": state.task_queue,
            "task_results": state.task_results,
            "final_verification": state.final_verification,
            "final_review": state.final_review,
            "review_only_input": state.review_only_input,
            "next_step_hint": review.next_step_hint if isinstance(review, ReviewOnlyReport) else None,
            "artifacts": state.artifacts,
        },
    )


def build_blocked_delivery(state: TeamState, reason: str) -> DeliveryPackage:
    """构建 blocked 交付包，确保阻断原因不会被隐藏。

    参数：
        state: 当前 TeamState。
        reason: 阻断原因。

    返回：
        status=blocked 的 DeliveryPackage。
    """
    changed_files: list[str] = []
    verification: list[VerificationResult] = []
    final_review = None

    for task_result in state.task_results:
        implementation = task_result.get("implementation") or {}
        for path in implementation.get("changed_files") or []:
            if path not in changed_files:
                changed_files.append(path)

        verification_data = task_result.get("verification")
        if verification_data:
            try:
                verification.append(VerificationResult.model_validate(verification_data))
            except Exception:
                pass

    if state.final_verification:
        try:
            verification.append(VerificationResult.model_validate(state.final_verification))
        except Exception:
            pass

    if state.final_review:
        try:
            final_review = FinalReviewReport.model_validate(state.final_review)
        except Exception:
            pass

    return build_delivery_package(
        state,
        status="blocked",
        reason=reason,
        summary=f"Blocked: {reason}",
        changed_files=changed_files,
        verification=verification,
        review=final_review,
        risks=[reason],
    )
