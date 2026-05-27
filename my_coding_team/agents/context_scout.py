"""Repository context scout."""

from __future__ import annotations

from pathlib import Path

from my_coding_team.orchestration.permission_builder import (
    build_readonly_probe_deny_rules,
    build_readonly_probe_rules,
)
from my_coding_team.runtime.prompts import load_prompt
from my_coding_team.schemas.common import Evidence
from my_coding_team.schemas.workflow import RepoContext, WorkspaceRecord


def make_context_scout_agent(model):
    """构建 ContextScout Agent，注册只读文件检索和 Bash 探查工具。

    参数：
        model: AgentScope 使用的聊天模型实例。

    返回：
        已配置为 DONT_ASK + 只读 allow/deny 规则的 Agent 实例。
    """
    from my_coding_team.runtime.agentscope_adapter import Bash, Glob, Grep, PermissionMode, Read
    from my_coding_team.runtime.factory import create_agent

    return create_agent(
        name="ContextScout",
        system_prompt=load_prompt("context_scout"),
        model=model,
        tools=[Read(), Grep(), Glob(), Bash()],
        permission_mode=PermissionMode.DONT_ASK,
        allow_rules=build_readonly_probe_rules(),
        deny_rules=build_readonly_probe_deny_rules(),
    )


async def call_context_scout(request: str, workspace: WorkspaceRecord, model=None) -> RepoContext:
    """收集仓库上下文，生成 Phase 6 使用的 RepoContext。

    参数：
        request: 用户原始请求。
        workspace: Workspace Manager 生成的工作区记录。
        model: 可选模型实例；MVP 当前使用确定性本地扫描。

    返回：
        包含相关文件、测试入口、构建命令、风险和 evidence 的 RepoContext。
    """
    root = Path(workspace.root)
    files = _candidate_files(root)
    tests = [path for path in files if path.startswith("tests/") and path.endswith(".py")]
    build_commands = ["python -m pytest"] if tests else []
    evidence = [Evidence(path=files[0], note="first relevant file")] if files else []
    risks = ["workspace has uncommitted changes"] if workspace.dirty_files else []
    return RepoContext(
        relevant_files=files[:20],
        test_entrypoints=tests[:10],
        build_commands=build_commands,
        risks=risks,
        evidence=evidence,
    )


def _candidate_files(root: Path) -> list[str]:
    """扫描适合作为上下文的源码/文档文件。

    参数：
        root: 仓库根目录。

    返回：
        排序后的仓库相对路径列表。
    """
    ignored = {".git", ".venv", ".pip-cache", ".pytest_cache", "__pycache__"}
    results: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        # 过滤依赖、缓存和 Git 元数据，避免把无关内容喂给上下文阶段。
        if any(part in ignored for part in path.parts):
            continue
        # MVP 只收集 Python、Markdown、TOML，覆盖当前项目主要事实来源。
        if path.suffix.lower() in {".py", ".md", ".toml"}:
            results.append(path.relative_to(root).as_posix())
    return sorted(results)
