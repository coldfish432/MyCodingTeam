"""AgentScope factory wrapper."""

from __future__ import annotations

from my_coding_team.runtime.agentscope_adapter import (
    Agent,
    AgentState,
    PermissionContext,
    PermissionMode,
    Toolkit,
)


def create_agent(
    *,
    name: str,
    system_prompt: str,
    model,
    tools: list | None = None,
    permission_mode: PermissionMode = PermissionMode.DEFAULT,
    allow_rules: dict | None = None,
    deny_rules: dict | None = None,
    working_directories: dict | None = None,
) -> Agent:
    """统一创建 AgentScope Agent 并注入权限上下文。

    参数：
        name: Agent 名称。
        system_prompt: 系统提示词。
        model: AgentScope 聊天模型实例。
        tools: 注册到 Toolkit 的工具列表。
        permission_mode: AgentScope PermissionMode。
        allow_rules: 允许规则字典。
        deny_rules: 拒绝规则字典。
        working_directories: 额外工作目录配置。

    返回：
        已配置 Toolkit 和 PermissionContext 的 Agent 实例。
    """
    return Agent(
        name=name,
        system_prompt=system_prompt,
        model=model,
        toolkit=Toolkit(tools=tools or []),
        state=AgentState(
            permission_context=PermissionContext(
                mode=permission_mode,
                allow_rules=allow_rules or {},
                deny_rules=deny_rules or {},
                working_directories=working_directories or {},
            ),
        ),
    )
