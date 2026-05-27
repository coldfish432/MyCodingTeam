"""Phase 7 lightweight build loop."""

from __future__ import annotations

from pathlib import Path

from my_coding_team.agents.context_scout import call_context_scout
from my_coding_team.agents.delivery import build_delivery_package
from my_coding_team.agents.planning import call_planning_for_single_contract
from my_coding_team.orchestration.task_runner import run_single_task
from my_coding_team.orchestration.workspace_manager import inspect_git_workspace
from my_coding_team.schemas.workflow import TeamState


async def run_lightweight(state: TeamState, *, workspace_root: str | Path, model=None):
    """运行 Phase 7 Lightweight Build Loop。

    参数：
        state: 当前 TeamState。
        workspace_root: 要读取和修改的工作区根目录。
        model: 真实或 mock 模型，用于 planning 和 implementation。

    返回：
        DeliveryPackage，包含修改文件、验证结果、审查结果和风险。
    """
    workspace = inspect_git_workspace(workspace_root)
    state.workspace = workspace
    state.current_phase = "workspace_prepared"
    repo_context = await call_context_scout(state.request, workspace, model=None)
    state.repo_context = repo_context
    state.current_phase = "context_collected"
    contract = await call_planning_for_single_contract(state.request, repo_context, workspace, model=model)
    state.artifacts["task_contract"] = contract.model_dump()
    state.current_phase = "planned"
    if model is not None:
        state.llm_calls_used += 1
    result = await run_single_task(contract, workspace.root, implementation_model=model)
    if model is not None:
        state.llm_calls_used += 1 + result.repair_attempts
    state.current_phase = "reviewed"
    status = "blocked" if result.blocked or not result.review.approval else "success"
    reason = result.blocked_reason or ("lightweight_completed" if status == "success" else "review_blocked")
    return build_delivery_package(
        state,
        status=status,
        reason=reason,
        summary=result.review.summary,
        changed_files=result.implementation.changed_files,
        verification=[result.verification],
        review=result.review,
        risks=repo_context.risks,
    )
