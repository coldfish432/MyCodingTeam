"""Single-task runner for Phase 7 MVP."""

from __future__ import annotations

from pathlib import Path

from my_coding_team.agents.qa_verification import call_qa_verification
from my_coding_team.agents.review_room import call_review_room
from my_coding_team.agents.task_implementation import call_task_implementation
from my_coding_team.schemas.common import Evidence
from my_coding_team.schemas.review import TaskReviewResult
from my_coding_team.schemas.task import (
    ImplementationResult,
    TaskContract,
    TaskRepairContract,
    VerificationResult,
)


class TaskRunnerResult:
    """Task Runner 内部结果对象。

    字段：
        implementation: 实现阶段结果。
        verification: 验证阶段结果。
        review: 审查阶段结果。
        repair_attempts: 已执行 repair 次数。
        blocked: 是否被阻断。
        blocked_reason: 阻断原因。
    """

    def __init__(
        self,
        *,
        implementation: ImplementationResult,
        verification: VerificationResult,
        review: TaskReviewResult,
        repair_attempts: int,
        blocked: bool,
        blocked_reason: str | None = None,
    ) -> None:
        """保存单任务运行的最终状态。"""
        self.implementation = implementation
        self.verification = verification
        self.review = review
        self.repair_attempts = repair_attempts
        self.blocked = blocked
        self.blocked_reason = blocked_reason


async def run_single_task(
    contract: TaskContract,
    workspace_root: str | Path,
    *,
    implementation_model=None,
    repair_model=None,
    max_repairs: int = 2,
) -> TaskRunnerResult:
    """执行单任务实现、验证、审查和最多两次 repair。

    参数：
        contract: 当前任务合同。
        workspace_root: 任务运行的工作区根目录。
        implementation_model: 实现阶段使用的真实或 mock 模型。
        repair_model: repair 阶段可选模型；为空时复用 implementation_model。
        max_repairs: 最大 repair 次数。

    返回：
        TaskRunnerResult，包含 implementation、verification、review 和阻断原因。
    """
    attempts = 0
    current_contract: TaskContract | TaskRepairContract = contract
    model = implementation_model
    while True:
        try:
            implementation = await call_task_implementation(current_contract, workspace_root, model=model)
        except PermissionError as exc:
            # 权限错误是安全阻断，不应让 CLI 崩溃，也不能继续执行验证命令。
            implementation = ImplementationResult(
                task_id=contract.task_id,
                success=False,
                summary=str(exc),
                changed_files=[],
                evidence=[Evidence(path=".", note=str(exc))],
            )
            verification = VerificationResult(
                task_id=contract.task_id,
                passed=False,
                commands=list(contract.verification_commands),
                failed_commands=list(contract.verification_commands),
                output_summary=f"not_run permission denied: {exc}",
                evidence=[Evidence(path=".", note="permission denied before verification")],
            )
            review = await call_review_room(contract, implementation, verification)
            return TaskRunnerResult(
                implementation=implementation,
                verification=verification,
                review=review,
                repair_attempts=attempts,
                blocked=True,
                blocked_reason="blocked_by_permission_denied",
            )
        verification = await call_qa_verification(current_contract, workspace_root)
        review = await call_review_room(contract, implementation, verification)
        if review.approval:
            # 审查通过即完成当前任务；Phase 7 不做额外 final review。
            return TaskRunnerResult(
                implementation=implementation,
                verification=verification,
                review=review,
                repair_attempts=attempts,
                blocked=False,
            )
        if attempts >= max_repairs:
            # repair 次数达到上限后硬阻断，避免无限循环和成本失控。
            return TaskRunnerResult(
                implementation=implementation,
                verification=verification,
                review=review,
                repair_attempts=attempts,
                blocked=True,
                blocked_reason="blocked_by_repair_limit",
            )
        attempts += 1
        # repair 合同继承原合同的文件和命令边界，只改变修复原因。
        current_contract = TaskRepairContract(
            original_task_id=contract.task_id,
            reason="; ".join(item for finding in review.findings for item in finding.must_fix),
            allowed_files=contract.allowed_files,
            verification_commands=contract.verification_commands,
            evidence=contract.evidence,
        )
        model = repair_model or implementation_model
