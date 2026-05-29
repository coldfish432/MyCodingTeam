"""Phase 9 Full Product Flow — 复杂需求从 Shape 到 Final Delivery 的完整闭环。

9a: Shape → Specification → Design Signoff
9b: TaskQueue → 多任务执行
9c: Final Verification → Final Review → Global Repair → Branch Finisher → Delivery
"""

from __future__ import annotations

from pathlib import Path

import my_coding_team.agents.context_scout  # noqa: F401
import my_coding_team.agents.planning  # noqa: F401
import my_coding_team.agents.qa_verification  # noqa: F401
import my_coding_team.agents.shape  # noqa: F401
import my_coding_team.agents.specification  # noqa: F401
import my_coding_team.rooms.review_room  # noqa: F401
from my_coding_team.agents.delivery import build_blocked_delivery, build_delivery_package
from my_coding_team.core.registry import ROOMS, STEPS
from my_coding_team.core.step import StepContext
from my_coding_team.orchestration.state_machine import transition
from my_coding_team.orchestration.task_runner import execute_task_queue
from my_coding_team.orchestration.workspace_manager import inspect_git_workspace
from my_coding_team.orchestration.signoff import request_design_signoff_cli
from my_coding_team.schemas.room_inputs import ReviewRoomInput
from my_coding_team.schemas.step_inputs import (
    ContextScoutInput,
    PlanningQueueInput,
    PlanningSingleInput,
    QAVerificationInput,
    ShapeInput,
    SpecificationInput,
)
from my_coding_team.schemas.workflow import ProductBrief, TeamState


async def run_full_product(
    state: TeamState,
    *,
    workspace_root: str | Path,
    model=None,
):
    """运行完整 Full Product Flow。

    参数：
        state: 当前 TeamState。
        workspace_root: 工作区根目录。
        model: 真实或 mock 模型。

    返回：
        DeliveryPackage。
    """
    # ── Phase 9a: Shape → Specification → Design Signoff ──
    state = await _run_phase_9a(state, model=model)
    if state.blocked_reason or state.current_phase not in (
        "planning_task_queue",
        "context_collected",
    ):
        return _build_blocked_from_state(state)

    # ── Phase 9b: Workspace + Scout + Planning Queue + Execute Tasks ──
    state = await _run_phase_9b(state, workspace_root=workspace_root, model=model)
    if state.blocked_reason:
        return _build_blocked_from_state(state)

    # ── Phase 9c: Final Verification → Final Review → Global Repair → Branch Finisher ──
    state = await _run_phase_9c(state, workspace_root=workspace_root, model=model)
    if state.blocked_reason:
        return _build_blocked_from_state(state)

    return _build_success_delivery(state)


async def _run_phase_9a(state: TeamState, *, model=None) -> TeamState:
    """Shape → Specification → Design Signoff。

    返回：
        更新后的 TeamState；signoff 阶段停在 planning_task_queue。
    """
    # Step 1: Shape
    transition(state.current_phase, "shaping")
    state.current_phase = "shaping"
    route_dict = state.route_decision.model_dump() if state.route_decision else None
    ctx = StepContext(model=model)
    frame = await STEPS["shape"].run(ShapeInput(request=state.request, route=route_dict), ctx)
    state.problem_frame = frame

    # Step 2: Specification
    transition(state.current_phase, "specifying")
    state.current_phase = "specifying"
    brief = await STEPS["specification"].run(
        SpecificationInput(problem_frame=frame.model_dump()),
        ctx,
    )
    state.product_brief = brief
    state.llm_calls_used += ctx.llm_call_charge

    # Step 3: Design Signoff
    transition(state.current_phase, "awaiting_design_signoff")
    state.current_phase = "awaiting_design_signoff"
    signoff = request_design_signoff_cli(brief)
    state.design_signoff = signoff

    if not signoff.permission_to_plan:
        transition(state.current_phase, "blocked_by_user_decision")
        state.current_phase = "blocked_by_user_decision"
        state.blocked_reason = signoff.reason or "user_declined_signoff"
        return state

    # 9a 完成，进入 9b
    transition(state.current_phase, "planning_task_queue")
    state.current_phase = "planning_task_queue"
    return state


async def _run_phase_9b(
    state: TeamState,
    *,
    workspace_root: str | Path,
    model=None,
) -> TeamState:
    """Workspace → Context Scout → Planning Queue → Multi-task 执行。

    使用 PlanningQueueStep 生成 TaskQueue，execute_task_queue 多任务顺序执行。
    预算预检在执行前生效。
    """
    # Workspace
    workspace = inspect_git_workspace(workspace_root)
    state.workspace = workspace
    transition(state.current_phase, "workspace_prepared")
    state.current_phase = "workspace_prepared"

    if workspace.dirty_files:
        state.blocked_reason = "dirty_worktree_needs_user_decision"
        return state

    # Context Scout
    ctx = StepContext(model=model, workspace_root=workspace.root)
    repo_context = await STEPS["context_scout"].run(
        ContextScoutInput(request=state.request, workspace=workspace),
        ctx,
    )
    state.repo_context = repo_context
    transition(state.current_phase, "context_collected")
    state.current_phase = "context_collected"

    # Planning — 输出 TaskQueue
    transition(state.current_phase, "planning_task_queue")
    state.current_phase = "planning_task_queue"

    brief = None
    if state.product_brief:
        try:
            brief = ProductBrief.model_validate(
                state.product_brief.model_dump()
                if hasattr(state.product_brief, 'model_dump')
                else state.product_brief
            )
        except Exception:
            pass

    if brief is not None:
        queue = await STEPS["planning_queue"].run(
            PlanningQueueInput(brief=brief.model_dump(), repo_context=repo_context.model_dump()),
            ctx,
        )
    else:
        # 没有 ProductBrief 时用单任务 fallback
        contract = await STEPS["planning_single"].run(
            PlanningSingleInput(
                request=state.request,
                repo_context=repo_context.model_dump(),
                workspace=workspace,
            ),
            ctx,
        )
        from my_coding_team.schemas.task import TaskItem, TaskQueue
        queue = TaskQueue(
            items=[TaskItem(
                task_id=contract.task_id,
                title=contract.goal[:80],
                description=contract.goal,
                files=contract.allowed_files,
                risk=contract.risk,
            )],
            strategy="sequential",
            estimated_total_calls=10,
        )

    state.task_queue = [item.model_dump() for item in queue.items]
    state.llm_calls_used += ctx.llm_call_charge

    # 预算预检
    if state.llm_calls_used + queue.estimated_total_calls > state.llm_calls_budget:
        state.blocked_reason = (
            f"budget_insufficient_for_queue: "
            f"used={state.llm_calls_used}, "
            f"estimated={queue.estimated_total_calls}, "
            f"budget={state.llm_calls_budget}"
        )
        state.current_phase = "blocked"
        return state

    # Execute multi-task queue
    transition(state.current_phase, "executing_task")
    state.current_phase = "executing_task"
    task_results = await execute_task_queue(
        queue,
        repo_context,
        workspace.root,
        state,
        model=model,
    )

    # 检查是否有 blocked
    blocked = [r for r in task_results if r.status != "completed"]
    if blocked:
        first = blocked[0]
        state.blocked_reason = f"task_{first.task_id}_{first.status}"
        return state

    # Task-level RED/GREEN updates may leave current_phase at a task sub-state
    # such as "implemented"; restore the workflow-level queue phase before 9c.
    state.current_phase = "executing_task"
    transition(state.current_phase, "final_verifying")
    state.current_phase = "final_verifying"
    return state


async def _run_phase_9c(
    state: TeamState,
    *,
    workspace_root: str | Path,
    model=None,
) -> TeamState:
    """Final Verification → Final Review → Global Repair → Branch Finisher → 完成。"""
    from my_coding_team.orchestration.branch_finisher import decide_branch_finish
    from my_coding_team.schemas.task import TaskRunResult, VerificationResult as VerRes
    from my_coding_team.schemas.review import FinalReviewReport
    from my_coding_team.schemas.workflow import ProductBrief

    # 收集所有任务的验证命令作为 final commands
    final_commands: list[str] = []
    if state.repo_context and state.repo_context.build_commands:
        final_commands.extend(state.repo_context.build_commands)
    for tr_dict in state.task_results:
        ver_data = tr_dict.get("verification", {})
        commands = ver_data.get("commands", [])
        for cmd in commands:
            if cmd not in final_commands:
                final_commands.append(cmd)

    if not final_commands:
        final_commands = ["python -m pytest"] if (
            state.repo_context and state.repo_context.test_entrypoints
        ) else ["python -m my_coding_team doctor"]

    # Final Verification
    if state.current_phase != "final_verifying":
        transition(state.current_phase, "final_verifying")
    state.current_phase = "final_verifying"
    final_ver = await STEPS["qa_verification"].run(
        QAVerificationInput(
            scope="final",
            commands=final_commands,
            workspace_root=str(workspace_root),
        ),
        StepContext(workspace_root=str(workspace_root)),
    )
    state.final_verification = final_ver.model_dump()

    # Final Review
    transition(state.current_phase, "final_reviewing")
    state.current_phase = "final_reviewing"

    # 重建 task_results
    task_run_results: list[TaskRunResult] = []
    for tr_dict in state.task_results:
        try:
            task_run_results.append(TaskRunResult.model_validate(tr_dict))
        except Exception:
            pass

    brief = None
    if state.product_brief:
        try:
            brief = ProductBrief.model_validate(state.product_brief.model_dump() if hasattr(state.product_brief, 'model_dump') else state.product_brief)
        except Exception:
            pass

    final_review = await ROOMS["review_room"].execute(
        ReviewRoomInput(
            scope="final",
            brief=brief.model_dump() if brief else None,
            task_results=[item.model_dump() for item in task_run_results],
            final_verification=final_ver.model_dump(),
        ),
        StepContext(model=model),
    )
    if model is not None:
        state.llm_calls_used += 1
    if isinstance(final_review, FinalReviewReport):
        state.final_review = final_review.model_dump()

        # Global Repair Loop — 最多 2 次尝试
        if final_review.findings and any(f.must_fix for f in final_review.findings):
            MAX_GLOBAL_REPAIR_ATTEMPTS = 2
            attempt = 0
            while (final_review.findings and any(f.must_fix for f in final_review.findings)
                   and attempt < MAX_GLOBAL_REPAIR_ATTEMPTS):
                attempt += 1
                transition(state.current_phase, "global_repairing")
                state.current_phase = "global_repairing"
                # 重跑 final verification
                final_ver = await STEPS["qa_verification"].run(
                    QAVerificationInput(
                        scope="final",
                        commands=final_commands,
                        workspace_root=str(workspace_root),
                    ),
                    StepContext(workspace_root=str(workspace_root)),
                )
                state.final_verification = final_ver.model_dump()
                # 重跑 final review
                final_review = await ROOMS["review_room"].execute(
                    ReviewRoomInput(
                        scope="final",
                        brief=brief.model_dump() if brief else None,
                        task_results=[item.model_dump() for item in task_run_results],
                        final_verification=final_ver.model_dump(),
                    ),
                    StepContext(model=model),
                )
                if model is not None:
                    state.llm_calls_used += 1
                if isinstance(final_review, FinalReviewReport):
                    state.final_review = final_review.model_dump()

            if isinstance(final_review, FinalReviewReport) and not final_review.approval:
                transition(state.current_phase, "blocked_by_max_repair_retries_exceeded")
                state.current_phase = "blocked_by_max_repair_retries_exceeded"
                state.blocked_reason = (
                    f"global_repair_exhausted after {MAX_GLOBAL_REPAIR_ATTEMPTS} attempts; "
                    f"unresolved must_fix items: {len(final_review.findings)}"
                )
                return state

    # Branch Finisher
    transition(state.current_phase, "finishing_branch")
    state.current_phase = "finishing_branch"
    if state.workspace:
        finish = decide_branch_finish(
            state.workspace,
            final_ver if isinstance(final_ver, VerRes) else None,
            final_review if isinstance(final_review, FinalReviewReport) else None,
        )
        state.artifacts["branch_finish"] = {
            "action": finish.action,
            "reason": finish.reason,
            "suggested_commands": finish.suggested_commands,
        }

    transition(state.current_phase, "delivered")
    state.current_phase = "delivered"
    return state


def _build_blocked_from_state(state: TeamState):
    """从 blocked state 构建 blocked delivery。"""
    return build_blocked_delivery(
        state,
        state.blocked_reason or "unknown_blocked_reason",
    )


def _build_success_delivery(state: TeamState):
    """从成功 state 构建 delivery。"""
    import json

    changed_files: list[str] = []
    verification_list = []
    review_data = None

    if state.task_results:
        from my_coding_team.schemas.task import VerificationResult
        from my_coding_team.schemas.review import FinalReviewReport

        for task_result in state.task_results:
            for path in task_result.get("implementation", {}).get("changed_files", []):
                if path not in changed_files:
                    changed_files.append(path)

            ver_data = task_result.get("verification", {})
            if ver_data:
                verification_list.append(VerificationResult.model_validate(ver_data))

        if state.final_verification:
            verification_list.append(VerificationResult.model_validate(state.final_verification))

        if state.final_review:
            review_data = FinalReviewReport.model_validate(state.final_review)

    return build_delivery_package(
        state,
        status="success",
        reason="full_product_completed",
        summary="Full Product Flow completed successfully.",
        changed_files=changed_files,
        verification=verification_list,
        review=review_data,
    )
