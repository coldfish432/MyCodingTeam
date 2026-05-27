"""Merged ReviewRoom for MVP."""

from __future__ import annotations

from my_coding_team.schemas.common import Evidence
from my_coding_team.schemas.review import ReviewFinding, TaskReviewResult
from my_coding_team.schemas.task import ImplementationResult, TaskContract, VerificationResult


async def call_review_room(
    contract: TaskContract,
    implementation: ImplementationResult,
    verification: VerificationResult,
    model=None,
) -> TaskReviewResult:
    """执行 MVP 合并版 ReviewRoom 审查。

    参数：
        contract: 当前任务合同。
        implementation: 实现阶段输出。
        verification: QA Verification 输出。
        model: 预留模型参数；MVP 当前使用确定性审查规则。

    返回：
        TaskReviewResult；验证失败或越界修改会产生 must_fix 并拒绝 approval。
    """
    findings: list[ReviewFinding] = []
    if not verification.passed:
        findings.append(
            ReviewFinding(
                finding_id="verification_failed",
                title="Verification did not pass",
                severity="high",
                approval=False,
                must_fix=["Fix failing or missing verification before delivery."],
                evidence=[Evidence(path=".", note=verification.output_summary or "verification failed")],
            ),
        )
    unauthorized = [path for path in implementation.changed_files if path not in contract.allowed_files]
    if unauthorized:
        findings.append(
            ReviewFinding(
                finding_id="unauthorized_files",
                title="Implementation changed files outside allowed_files",
                severity="high",
                approval=False,
                must_fix=[f"Remove unauthorized changes: {', '.join(unauthorized)}"],
                evidence=[Evidence(path=unauthorized[0], note="changed outside contract")],
            ),
        )
    approval = not any(finding.must_fix for finding in findings)
    return TaskReviewResult(
        task_id=contract.task_id,
        approval=approval,
        summary="approved" if approval else "must_fix findings remain",
        findings=findings,
    )
