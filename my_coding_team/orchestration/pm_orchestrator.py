"""PM orchestrator state machine."""

from __future__ import annotations

from pathlib import Path

from my_coding_team.agents.delivery import build_blocked_delivery
from my_coding_team.agents import intake_router as _intake_router  # noqa: F401
from my_coding_team.core.registry import STEPS
from my_coding_team.core.step import StepContext
from my_coding_team.orchestration.cost_budget import BudgetExceededError, LlmBudget
from my_coding_team.schemas.step_inputs import IntakeRouterInput
from my_coding_team.schemas.workflow import TeamState
from my_coding_team.workflows.direct_answer import run_direct_answer
from my_coding_team.workflows.full_product import run_full_product
from my_coding_team.workflows.lightweight import run_lightweight
from my_coding_team.workflows.review_only import run_review_only


async def run_request(
    request: str,
    *,
    budget: int = 10,
    workspace: str | Path | None = None,
    mode: str = "auto",
    model=None,
    pasted_content: str | None = None,
):
    """运行 PM Orchestrator，按模式或路由结果进入 workflow。

    参数：
        request: 用户原始请求。
        budget: LLM 调用预算。
        workspace: 工作区路径；为空时使用当前目录。
        mode: auto、direct、lightweight 或 full。
        model: 真实或 mock 模型实例。

    返回：
        DeliveryPackage，表示成功、阻断或失败交付。
    """
    state = TeamState(request=request, llm_calls_budget=budget)
    budget_meter = LlmBudget(limit=budget)
    try:
        if budget <= 0 and model is not None:
            budget_meter.charge()
        normalized_mode = "review_only" if mode == "review-only" else mode
        if normalized_mode == "direct":
            workflow = "direct_answer"
            route = None
        elif normalized_mode == "lightweight":
            workflow = "lightweight"
            route = None
        elif normalized_mode == "full":
            workflow = "full"
            route = None
        elif normalized_mode == "review_only":
            workflow = "review_only"
            route = None
        else:
            route = await STEPS["intake_router"].run(IntakeRouterInput(request=request), StepContext(model=None))
            workflow = route.workflow
            state.route_decision = route
        state.workflow = workflow
        state.current_phase = "routed"
        if workflow == "direct_answer":
            if model is not None:
                budget_meter.charge()
            return await run_direct_answer(state, model=model)
        if workflow == "lightweight":
            if model is not None:
                budget_meter.charge(2)
            return await run_lightweight(state, workspace_root=workspace or Path.cwd(), model=model)
        if workflow == "full":
            return await run_full_product(state, workspace_root=workspace or Path.cwd(), model=model)
        if workflow == "review_only":
            if model is not None:
                budget_meter.charge(1)
            return await run_review_only(
                state,
                workspace_root=workspace or Path.cwd(),
                model=model,
                pasted_content=pasted_content,
            )
        return build_blocked_delivery(state, f"{workflow}_not_implemented_in_mvp")
    except BudgetExceededError as exc:
        state.status = "blocked"
        return build_blocked_delivery(state, str(exc))
