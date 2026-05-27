"""PM orchestrator state machine."""

from __future__ import annotations

from pathlib import Path

from my_coding_team.agents.delivery import build_blocked_delivery
from my_coding_team.agents.intake_router import call_intake_router
from my_coding_team.orchestration.cost_budget import BudgetExceededError, LlmBudget
from my_coding_team.schemas.workflow import TeamState
from my_coding_team.workflows.direct_answer import run_direct_answer
from my_coding_team.workflows.lightweight import run_lightweight


async def run_request(
    request: str,
    *,
    budget: int = 10,
    workspace: str | Path | None = None,
    mode: str = "auto",
    model=None,
):
    """运行 PM Orchestrator，按模式或路由结果进入 MVP workflow。

    参数：
        request: 用户原始请求。
        budget: LLM 调用预算。
        workspace: 工作区路径；为空时使用当前目录。
        mode: auto、direct 或 lightweight。
        model: 真实或 mock 模型实例。

    返回：
        DeliveryPackage，表示成功、阻断或失败交付。
    """
    state = TeamState(request=request, llm_calls_budget=budget)
    budget_meter = LlmBudget(limit=budget)
    try:
        if budget <= 0 and model is not None:
            budget_meter.charge()
        if mode == "direct":
            workflow = "direct_answer"
            route = None
        elif mode == "lightweight":
            workflow = "lightweight"
            route = None
        else:
            route = await call_intake_router(request, model=None)
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
        return build_blocked_delivery(state, f"{workflow}_not_implemented_in_mvp")
    except BudgetExceededError as exc:
        state.status = "blocked"
        return build_blocked_delivery(state, str(exc))
