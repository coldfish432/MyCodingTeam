"""Single-task and multi-task runner for lightweight and full workflows."""

from __future__ import annotations

import re
from pathlib import Path

import my_coding_team.rooms.implementation_room  # noqa: F401
import my_coding_team.rooms.review_room  # noqa: F401
import my_coding_team.rooms.tdd_room  # noqa: F401
from my_coding_team.core.registry import ROOMS, STEPS
from my_coding_team.core.step import StepContext
from my_coding_team.schemas.room_inputs import ImplementationRoomInput, ReviewRoomInput, TDDRoomInput
from my_coding_team.schemas.step_inputs import QAVerificationInput
from my_coding_team.schemas.common import Evidence
from my_coding_team.schemas.review import ReviewFinding, TaskReviewResult
from my_coding_team.schemas.task import (
    ImplementationResult,
    RedResult,
    TaskContract,
    TaskItem,
    TaskQueue,
    TaskRepairContract,
    TaskRunResult,
    VerificationResult,
)
from my_coding_team.schemas.workflow import RepoContext, TeamState

import my_coding_team.agents.qa_verification  # noqa: F401


ACCEPTABLE_RED_CATEGORIES = {"assertion", "not_implemented", "import_error"}
UNACCEPTABLE_RED_CATEGORIES = {"syntax_error", "collection_error"}


class TaskRunnerResult:
    """Result object for a single task run."""

    def __init__(
        self,
        *,
        implementation: ImplementationResult,
        verification: VerificationResult,
        review: TaskReviewResult,
        repair_attempts: int,
        blocked: bool,
        blocked_reason: str | None = None,
        red: RedResult | None = None,
    ) -> None:
        self.implementation = implementation
        self.verification = verification
        self.review = review
        self.repair_attempts = repair_attempts
        self.blocked = blocked
        self.blocked_reason = blocked_reason
        self.red = red


def verify_red(red: RedResult) -> tuple[bool, str | None]:
    """Validate that a RED result is a useful expected failure."""
    if red.red_type == "skip":
        if red.skip_reason:
            return True, None
        return False, "skip without reason"

    if not red.expected_failure_signature:
        return False, "missing expected_failure_signature"
    if not red.actual_output:
        return False, "missing actual_output"
    if red.failure_category in UNACCEPTABLE_RED_CATEGORIES:
        return False, f"unacceptable failure category: {red.failure_category}"
    if red.failure_category == "other":
        return False, "failure_category=other requires manual review"
    if red.failure_category not in ACCEPTABLE_RED_CATEGORIES:
        return False, "missing or invalid failure_category"

    tokens = [token for token in re.split(r"\W+", red.expected_failure_signature) if len(token) > 3]
    if not tokens:
        return False, "expected_failure_signature has no meaningful tokens (len>3)"

    output_lower = red.actual_output.lower()
    missing = [token for token in tokens if token.lower() not in output_lower]
    if missing:
        return False, f"actual_output missing tokens: {missing}"
    return True, None


def should_run_red(
    contract: TaskContract,
    repo_context: RepoContext | None = None,
    state: TeamState | None = None,
) -> bool:
    """Combine planner intent with deterministic PM rules for RED execution."""
    pm_rule, reason = _pm_heuristic(contract, repo_context)
    planning_says = contract.test_first_requirement

    if planning_says == "not_applicable" and pm_rule is True:
        result = True
    elif planning_says == "required" and pm_rule is False:
        result = False
    elif planning_says == "required":
        result = True
    elif planning_says == "not_applicable":
        result = False
    else:
        result = pm_rule

    planning_bool = None
    if planning_says == "required":
        planning_bool = True
    elif planning_says == "not_applicable":
        planning_bool = False
    if state is not None and planning_bool is not None and planning_bool != pm_rule:
        state.pm_overrides.append(
            {
                "point": "should_run_red",
                "planning_said": planning_says,
                "pm_said": pm_rule,
                "final": result,
                "reason": reason,
            }
        )
    return result


def _pm_heuristic(contract: TaskContract, repo_context: RepoContext | None = None) -> tuple[bool, str]:
    if not contract.verification_commands and not contract.red_verification_command:
        return False, "no verification command"
    if repo_context is not None and not repo_context.test_entrypoints:
        return False, "no test entrypoints in repo context"

    doc_exts = (".md", ".rst", ".txt", ".adoc")
    config_exts = (".toml", ".yaml", ".yml", ".json", ".ini", ".cfg")
    if all(any(path.endswith(ext) for ext in doc_exts + config_exts) for path in contract.allowed_files):
        return False, "all allowed files are docs/config"
    return True, "code-like files with verification available"


async def run_single_task_with_red(
    contract: TaskContract,
    workspace_root: str | Path,
    *,
    state: TeamState | None = None,
    tdd_model=None,
    implementation_model=None,
    repair_model=None,
    max_repairs: int = 2,
    repo_context: RepoContext | None = None,
) -> TaskRunnerResult:
    """Run optional RED before the implementation and verification loop."""
    red: RedResult | None = None
    if should_run_red(contract, repo_context=repo_context, state=state):
        if state is not None:
            state.current_phase = "writing_red"
        try:
            red_output = await ROOMS["tdd_room"].execute(
                TDDRoomInput(
                    contract=contract.model_dump(),
                    workspace_root=str(workspace_root),
                ),
                StepContext(model=tdd_model or implementation_model, workspace_root=str(workspace_root)),
            )
            red = RedResult.model_validate(red_output.red_result)
        except PermissionError as exc:
            red = RedResult(
                task_id=contract.task_id,
                red_type="test",
                command=contract.red_verification_command or "",
                actual_output=str(exc),
                failure_category="other",
                failure_excerpt=str(exc),
                evidence=[Evidence(path=".", note=str(exc))],
            )
        if state is not None:
            state.red_results.append(red.model_dump())
            state.llm_calls_used += 1
        ok, reason = verify_red(red)
        if not ok:
            return _blocked_red_result(contract, red, reason or "red mismatch")
        if state is not None:
            state.current_phase = "implemented"

    green_contract = _contract_with_red_verification(contract)
    result = await run_single_task(
        green_contract,
        workspace_root,
        implementation_model=implementation_model,
        repair_model=repair_model,
        max_repairs=max_repairs,
    )
    result.red = red
    if red is not None and result.review.approval:
        result.review = await ROOMS["review_room"].execute(
            ReviewRoomInput(
                scope="task",
                contract=contract.model_dump(),
                implementation=result.implementation.model_dump(),
                verification=result.verification.model_dump(),
                red=red.model_dump(),
            ),
            StepContext(),
        )
        if not result.review.approval:
            result.blocked = True
            result.blocked_reason = "review_blocked"
    return result


def _contract_with_red_verification(contract: TaskContract) -> TaskContract:
    command = contract.red_verification_command
    if not command or command in contract.verification_commands:
        return contract
    return contract.model_copy(update={"verification_commands": [command, *contract.verification_commands]})


def _blocked_red_result(contract: TaskContract, red: RedResult, reason: str) -> TaskRunnerResult:
    implementation = ImplementationResult(
        task_id=contract.task_id,
        success=False,
        summary=f"RED mismatch: {reason}",
        changed_files=list(red.files_changed),
        evidence=[Evidence(path=".", note=reason)],
    )
    verification = VerificationResult(
        task_id=contract.task_id,
        passed=False,
        commands=[red.command] if red.command else [],
        failed_commands=[red.command] if red.command else [],
        output_summary=red.actual_output or reason,
        evidence=[Evidence(path=".", note="RED mismatch before GREEN")],
    )
    review = TaskReviewResult(
        task_id=contract.task_id,
        approval=False,
        summary="RED mismatch blocked task before implementation",
        findings=[
            ReviewFinding(
                finding_id="red_mismatch",
                title="RED result did not match expected failure",
                severity="high",
                approval=False,
                must_fix=[reason],
                evidence=[Evidence(path=".", note=red.actual_output or reason)],
            ),
        ],
    )
    return TaskRunnerResult(
        implementation=implementation,
        verification=verification,
        review=review,
        repair_attempts=0,
        blocked=True,
        blocked_reason="blocked_by_red_mismatch",
        red=red,
    )


async def run_single_task(
    contract: TaskContract,
    workspace_root: str | Path,
    *,
    implementation_model=None,
    repair_model=None,
    max_repairs: int = 2,
) -> TaskRunnerResult:
    """Run implementation, verification, ReviewRoom, and bounded repair."""
    attempts = 0
    current_contract: TaskContract | TaskRepairContract = contract
    model = implementation_model
    while True:
        try:
            implementation = await ROOMS["implementation_room"].execute(
                ImplementationRoomInput(
                    contract=current_contract.model_dump(),
                    workspace_root=str(workspace_root),
                ),
                StepContext(model=model, workspace_root=str(workspace_root)),
            )
        except PermissionError as exc:
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
            review = await ROOMS["review_room"].execute(
                ReviewRoomInput(
                    scope="task",
                    contract=contract.model_dump(),
                    implementation=implementation.model_dump(),
                    verification=verification.model_dump(),
                ),
                StepContext(),
            )
            return TaskRunnerResult(
                implementation=implementation,
                verification=verification,
                review=review,
                repair_attempts=attempts,
                blocked=True,
                blocked_reason="blocked_by_permission_denied",
            )

        verification = await STEPS["qa_verification"].run(
            QAVerificationInput(
                contract=current_contract.model_dump(),
                workspace_root=str(workspace_root),
            ),
            StepContext(workspace_root=str(workspace_root)),
        )
        review = await ROOMS["review_room"].execute(
            ReviewRoomInput(
                scope="task",
                contract=contract.model_dump(),
                implementation=implementation.model_dump(),
                verification=verification.model_dump(),
            ),
            StepContext(),
        )
        if review.approval:
            return TaskRunnerResult(
                implementation=implementation,
                verification=verification,
                review=review,
                repair_attempts=attempts,
                blocked=False,
            )
        if attempts >= max_repairs:
            return TaskRunnerResult(
                implementation=implementation,
                verification=verification,
                review=review,
                repair_attempts=attempts,
                blocked=True,
                blocked_reason="blocked_by_repair_limit",
            )

        attempts += 1
        repair_reason = "; ".join(item for finding in review.findings for item in finding.must_fix)
        extend_to_red = _review_requests_red_repair(review)
        repair_allowed_files = list(contract.allowed_files)
        if extend_to_red:
            repair_allowed_files = [*repair_allowed_files, *contract.red_allowed_files]
        current_contract = TaskRepairContract(
            original_task_id=contract.task_id,
            reason=repair_reason,
            allowed_files=repair_allowed_files,
            verification_commands=contract.verification_commands,
            red_allowed_files=contract.red_allowed_files,
            extend_allowed_files_to_red=extend_to_red,
            evidence=contract.evidence,
        )
        model = repair_model or implementation_model


def _review_requests_red_repair(review: TaskReviewResult) -> bool:
    for finding in review.findings:
        text = " ".join([finding.title, *finding.must_fix]).lower()
        if "red test" in text or "test quality" in text or "test file" in text:
            return True
    return False


async def execute_task_queue(
    queue: TaskQueue,
    repo_context: RepoContext,
    workspace_root: str | Path,
    state: TeamState,
    *,
    model=None,
    max_repairs: int = 2,
) -> list[TaskRunResult]:
    """Phase 9b: 多任务队列顺序执行。

    每个任务独立 contract、独立 implementation、独立 verification、独立 review。
    任务 N 有 unresolved must_fix 会阻塞任务 N+1。

    参数：
        queue: Planning 输出的 TaskQueue。
        repo_context: Context Scout 输出，供每个任务 contract 生成使用。
        workspace_root: 工作区根目录。
        state: 共享 TeamState。
        model: 真实或 mock 模型。
        max_repairs: 每个任务最大 repair 次数。

    返回：
        TaskRunResult 列表。
    """
    results: list[TaskRunResult] = []
    completed_summaries: list[dict] = []

    for item in queue.items:
        # 生成 contract，注入 prior summaries
        contract = _build_contract_from_item(item, repo_context, completed_summaries)
        state.artifacts[f"contract_{item.task_id}"] = contract.model_dump()

        # 执行单任务
        runner_result = await run_single_task_with_red(
            contract,
            workspace_root,
            state=state,
            implementation_model=model,
            repo_context=repo_context,
            max_repairs=max_repairs,
        )
        if model is not None:
            state.llm_calls_used += 1 + runner_result.repair_attempts

        # 转换为 TaskRunResult
        status = "completed"
        if runner_result.blocked:
            if runner_result.blocked_reason == "blocked_by_red_mismatch":
                status = "blocked_red_mismatch"
            elif runner_result.blocked_reason == "blocked_by_permission_denied":
                status = "blocked_permission_denied"
            elif runner_result.blocked_reason == "blocked_by_repair_limit":
                status = "blocked_repair_limit"
            elif not runner_result.review.approval:
                status = "blocked_must_fix"
            else:
                status = "blocked_must_fix"

        task_result = TaskRunResult(
            task_id=item.task_id,
            status=status,
            implementation=runner_result.implementation,
            verification=runner_result.verification,
            review=runner_result.review.model_dump(),
            repair_attempts=runner_result.repair_attempts,
        )
        results.append(task_result)
        state.task_results.append(task_result.model_dump())

        # 失败 → 停止队列
        if status != "completed":
            state.blocked_reason = f"task_{item.task_id}_{status}"
            break

        # 累积 prior task summary
        completed_summaries.append({
            "task_id": item.task_id,
            "files_changed": runner_result.implementation.changed_files,
            "summary": runner_result.implementation.summary,
        })

    return results


def _build_contract_from_item(
    item: TaskItem,
    repo_context: RepoContext,
    prior_summaries: list[dict],
) -> TaskContract:
    """从 TaskItem 构建 TaskContract。

    参数：
        item: 任务队列条目。
        repo_context: 仓库上下文。
        prior_summaries: 已完成任务摘要列表。

    返回：
        TaskContract，其中 allowed_files 来自 item.files。
    """
    allowed_files = list(item.files) if item.files else repo_context.relevant_files[:1]
    command = "python -m pytest" if repo_context.test_entrypoints else "python -m my_coding_team doctor"

    # 判断是否需要 RED
    doc_exts = (".md", ".rst", ".txt", ".adoc")
    config_exts = (".toml", ".yaml", ".yml", ".json", ".ini", ".cfg")
    is_docs_config = all(
        any(path.endswith(ext) for ext in doc_exts + config_exts)
        for path in allowed_files
    )
    test_first = "not_applicable" if is_docs_config else "required"

    return TaskContract(
        task_id=item.task_id,
        goal=f"{item.title}: {item.description}" if item.description else item.title,
        allowed_files=allowed_files,
        verification_commands=[command],
        risk=item.risk,
        evidence=[Evidence(path=allowed_files[0], note=f"from TaskItem {item.task_id}")],
        test_first_requirement=test_first,
        red_allowed_files=["tests/**"],
        red_verification_command=command,
        prior_task_summaries=prior_summaries,
    )
