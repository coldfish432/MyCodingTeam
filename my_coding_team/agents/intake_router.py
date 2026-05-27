"""Intake routing agent facade."""

from __future__ import annotations

from my_coding_team.runtime.middleware import parse_schema
from my_coding_team.runtime.prompts import load_prompt
from my_coding_team.schemas.workflow import RouteDecision


def route_request_deterministically(request: str) -> RouteDecision:
    """用确定性规则对用户请求进行 MVP 路由。

    参数：
        request: 用户原始请求文本。

    返回：
        RouteDecision，包含 workflow、risk、confidence 和路由理由。
    """
    text = request.lower().strip()
    if not text:
        return RouteDecision(
            workflow="direct_answer",
            risk="low",
            confidence=0.4,
            needs_clarification=True,
            clarification_questions=["What should the team do?"],
            rationale="empty request",
        )
    if any(word in text for word in ["review", "检查", "审查", "pr"]):
        return RouteDecision(workflow="review_only", risk="medium", confidence=0.8, rationale="review request")
    if any(word in text for word in ["架构", "系统", "完整流程", "cross-module", "full"]):
        return RouteDecision(workflow="full", risk="high", confidence=0.75, rationale="broad system request")
    if any(word in text for word in ["改", "修", "增加", "删除", "新增", "实现", "write", "fix", "add", "update"]):
        return RouteDecision(workflow="lightweight", risk="medium", confidence=0.8, rationale="small change request")
    return RouteDecision(workflow="direct_answer", risk="low", confidence=0.7, rationale="answer-only request")


def make_intake_router_agent(model):
    """构建 IntakeRouter Agent，注册只读检索工具。

    参数：
        model: AgentScope 使用的聊天模型实例。

    返回：
        已配置 EXPLORE 权限且不包含 Bash 的 Agent 实例。
    """
    from my_coding_team.runtime.agentscope_adapter import Glob, Grep, PermissionMode, Read
    from my_coding_team.runtime.factory import create_agent

    return create_agent(
        name="IntakeRouter",
        system_prompt=load_prompt("intake_router"),
        model=model,
        tools=[Read(), Grep(), Glob()],
        permission_mode=PermissionMode.EXPLORE,
    )


async def call_intake_router(request: str, model=None) -> RouteDecision:
    """调用 Intake Router，输出结构化路由决策。

    参数：
        request: 用户原始请求文本。
        model: 可选结构化模型；为空时使用确定性路由规则。

    返回：
        RouteDecision。
    """
    if model is None:
        return route_request_deterministically(request)
    prompt = f"{load_prompt('intake_router')}\n\nRequest:\n{request}"
    payload = await model.complete_json(prompt)
    return parse_schema(RouteDecision, payload)
