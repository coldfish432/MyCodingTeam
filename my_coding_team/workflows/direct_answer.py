"""Direct answer workflow."""

from __future__ import annotations

from my_coding_team.agents.delivery import build_delivery_package
from my_coding_team.schemas.workflow import TeamState


async def run_direct_answer(state: TeamState, model=None):
    """运行 Direct Answer workflow，不读写仓库。

    参数：
        state: 当前 TeamState。
        model: 可选真实或 mock 模型；为空时返回确定性摘要。

    返回：
        DeliveryPackage。
    """
    if model is None:
        answer = "Direct answer workflow completed without repository changes."
    else:
        answer = await model.complete_text(f"Answer this user request concisely:\n{state.request}")
        state.llm_calls_used += 1
    return build_delivery_package(
        state,
        status="success",
        reason="direct_answer_completed",
        summary=answer,
    )
