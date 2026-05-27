"""Delivery package construction."""

from __future__ import annotations

from my_coding_team.schemas.delivery import DeliveryPackage, FinishDecision
from my_coding_team.schemas.review import FinalReviewReport, TaskReviewResult
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
    review: TaskReviewResult | FinalReviewReport | None = None,
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
    return DeliveryPackage(
        request=state.request,
        decision=FinishDecision(status=status, reason=reason),
        summary=summary,
        changed_files=changed_files or [],
        verification=verification or [],
        review=final_review,
        risks=risks or [],
        llm_calls_used=state.llm_calls_used,
    )


def build_blocked_delivery(state: TeamState, reason: str) -> DeliveryPackage:
    """构建 blocked 交付包，确保阻断原因不会被隐藏。

    参数：
        state: 当前 TeamState。
        reason: 阻断原因。

    返回：
        status=blocked 的 DeliveryPackage。
    """
    return build_delivery_package(
        state,
        status="blocked",
        reason=reason,
        summary=f"Blocked: {reason}",
        risks=[reason],
    )
