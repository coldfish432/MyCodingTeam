"""Workspace inspection and AgentScope LocalWorkspace lifecycle helpers."""

from __future__ import annotations

import subprocess
from contextlib import asynccontextmanager
from pathlib import Path

from my_coding_team.runtime.agentscope_adapter import LocalWorkspace
from my_coding_team.schemas.common import Evidence
from my_coding_team.schemas.workflow import WorkspaceRecord


def inspect_git_workspace(workdir: str | Path) -> WorkspaceRecord:
    """检查本地工作区 Git 状态。

    参数：
        workdir: 要检查的目录。

    返回：
        WorkspaceRecord；非 Git 目录会降级为 is_git=false。
    """
    root = Path(workdir).resolve()
    is_git = _run_git(root, "rev-parse --is-inside-work-tree").returncode == 0
    if not is_git:
        return WorkspaceRecord(
            root=str(root),
            is_git=False,
            evidence=[Evidence(path=str(root), note="not a git repository")],
        )
    commit_result = _run_git(root, "rev-parse HEAD")
    status_result = _run_git(root, "status --short")
    status_short = status_result.stdout.strip()
    dirty_files = [
        line[3:].strip()
        for line in status_short.splitlines()
        if len(line) >= 3
    ]
    return WorkspaceRecord(
        root=str(root),
        is_git=True,
        current_commit=commit_result.stdout.strip() or None,
        status_short=status_short,
        dirty_files=dirty_files,
        evidence=[Evidence(path=str(root), note="git workspace inspected")],
    )


@asynccontextmanager
async def local_workspace(workdir: str | Path):
    """创建并关闭 AgentScope LocalWorkspace。

    参数：
        workdir: LocalWorkspace 根目录。

    返回：
        async context manager，yield 已初始化的 LocalWorkspace。
    """
    workspace = LocalWorkspace(workdir=str(Path(workdir).resolve()))
    initialize = getattr(workspace, "initialize", None)
    if initialize is not None:
        result = initialize()
        if hasattr(result, "__await__"):
            await result
    try:
        yield workspace
    finally:
        close = getattr(workspace, "close", None)
        if close is not None:
            result = close()
            if hasattr(result, "__await__"):
                await result


def _run_git(root: Path, args: str) -> subprocess.CompletedProcess[str]:
    """在指定目录运行 git 子命令并捕获输出。

    参数：
        root: 工作区目录。
        args: git 后面的参数字符串。

    返回：
        CompletedProcess，调用方根据 returncode 判断成功与否。
    """
    return subprocess.run(
        f"git {args}",
        cwd=root,
        shell=True,
        text=True,
        capture_output=True,
    )
