"""Task implementation facade with strict allowed-file enforcement."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

from my_coding_team.runtime.middleware import parse_schema
from my_coding_team.runtime.prompts import load_prompt
from my_coding_team.schemas.common import Evidence
from my_coding_team.schemas.task import ImplementationResult, TaskContract, TaskRepairContract


async def call_task_implementation(
    contract: TaskContract | TaskRepairContract,
    workspace_root: str | Path,
    model=None,
) -> ImplementationResult:
    """按任务合同应用实现改动，并强制限制在 allowed_files 内。

    参数：
        contract: TaskContract 或 TaskRepairContract。
        workspace_root: 要修改的工作区根目录。
        model: 真实或 mock 模型；为空时不改文件，只返回跳过结果。

    返回：
        ImplementationResult，包含 changed_files 和 evidence。

    异常：
        PermissionError: 模型请求写入未授权路径或危险路径。
    """
    if model is None:
        return ImplementationResult(
            task_id=_task_id(contract),
            success=True,
            summary="No model supplied; implementation skipped.",
            changed_files=[],
        )
    prompt = (
        f"{load_prompt('task_implementation')}\n\n"
        f"Contract:\n{contract.model_dump_json(indent=2)}"
    )
    payload = await model.complete_json(prompt)
    changes = payload.get("changes", [])
    changed_files = _apply_changes(Path(workspace_root), contract.allowed_files, changes)
    return ImplementationResult(
        task_id=_task_id(contract),
        success=True,
        summary=payload.get("summary", "implemented changes"),
        changed_files=changed_files,
        evidence=[Evidence(path=path, note="changed by task implementation") for path in changed_files],
    )


def make_task_impl_agent(contract, workspace, model):
    """构建 Task Implementation Agent，注册读写和验证工具。

    参数：
        contract: 当前任务合同，用于生成 allowed_files 权限规则。
        workspace: AgentScope workspace/offloader 实例。
        model: AgentScope 使用的聊天模型实例。

    返回：
        已配置 DONT_ASK + TaskContract allow_rules 的 Agent 实例。
    """
    from my_coding_team.orchestration.permission_builder import build_task_allow_rules
    from my_coding_team.runtime.agentscope_adapter import Bash, Edit, Glob, Grep, PermissionMode, Read, Write
    from my_coding_team.runtime.factory import create_agent

    return create_agent(
        name=f"TaskImpl-{_task_id(contract)}",
        system_prompt=load_prompt("task_implementation"),
        model=model,
        tools=[Read(), Grep(), Glob(), Write(), Edit(), Bash()],
        permission_mode=PermissionMode.DONT_ASK,
        allow_rules=build_task_allow_rules(contract),
    )


def _apply_changes(root: Path, allowed_files: list[str], changes: list[dict[str, Any]]) -> list[str]:
    """按模型输出应用文件替换，并执行路径授权检查。

    参数：
        root: 工作区根目录。
        allowed_files: 合同允许修改的路径模式。
        changes: 模型输出的变更列表。

    返回：
        实际写入的相对路径列表。

    异常：
        PermissionError: 路径为空、绝对路径、父级穿越或不在 allowed_files 内。
    """
    changed: list[str] = []
    for change in changes:
        rel_path = str(change.get("path", "")).replace("\\", "/").strip()
        # 先挡住路径穿越和绝对路径，再做 allowed_files 模式匹配。
        if not rel_path or rel_path.startswith("../") or Path(rel_path).is_absolute():
            raise PermissionError(f"Refusing unsafe path: {rel_path}")
        if not _is_allowed(rel_path, allowed_files):
            raise PermissionError(f"Path is outside allowed_files: {rel_path}")
        target = root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(change.get("content", "")), encoding="utf-8")
        changed.append(rel_path)
    return changed


def _is_allowed(path: str, allowed_files: list[str]) -> bool:
    """检查路径是否匹配合同 allowed_files。

    参数：
        path: 仓库相对路径。
        allowed_files: 合同允许路径或 glob。

    返回：
        True 表示允许写入。
    """
    for pattern in allowed_files:
        normalized = pattern.replace("\\", "/")
        if normalized.endswith("/"):
            normalized = f"{normalized}**"
        if fnmatch.fnmatch(path, normalized):
            return True
    return False


def _task_id(contract: TaskContract | TaskRepairContract) -> str:
    """从普通合同或 repair 合同中取任务 ID。"""
    return getattr(contract, "task_id", getattr(contract, "original_task_id", "repair"))
