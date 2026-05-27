"""Verification runner for task contracts."""

from __future__ import annotations

import subprocess
from pathlib import Path

from my_coding_team.schemas.common import Evidence
from my_coding_team.schemas.task import TaskContract, TaskRepairContract, VerificationResult


SAFE_PREFIXES = (
    "pytest",
    "python -m pytest",
    "py -m pytest",
    "python -m my_coding_team doctor",
)


async def call_qa_verification(
    contract: TaskContract | TaskRepairContract,
    workspace_root: str | Path,
    *,
    timeout_seconds: int = 60,
) -> VerificationResult:
    """运行 TaskContract 指定的安全验证命令。

    参数：
        contract: TaskContract 或 TaskRepairContract。
        workspace_root: 验证命令运行的工作区根目录。
        timeout_seconds: 单条命令超时时间。

    返回：
        VerificationResult，记录执行命令、失败命令、输出摘要和 evidence。
    """
    failed: list[str] = []
    summaries: list[str] = []
    for command in contract.verification_commands:
        if not _is_safe_command(command):
            failed.append(command)
            summaries.append(f"not_run unsafe command: {command}")
            continue
        result = subprocess.run(
            command,
            cwd=workspace_root,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        summaries.append(f"$ {command}\nexit={result.returncode}\n{output[-1200:]}")
        if result.returncode != 0:
            failed.append(command)
    passed = bool(contract.verification_commands) and not failed
    return VerificationResult(
        task_id=getattr(contract, "task_id", getattr(contract, "original_task_id", "repair")),
        passed=passed,
        commands=list(contract.verification_commands),
        failed_commands=failed,
        output_summary="\n\n".join(summaries),
        evidence=[Evidence(path=".", note="verification command output")],
    )


def _is_safe_command(command: str) -> bool:
    """判断验证命令是否在 MVP 安全白名单内。

    参数：
        command: 待运行命令。

    返回：
        True 表示允许运行；False 表示记录为 not_run。
    """
    normalized = " ".join(command.strip().split())
    return any(normalized == prefix or normalized.startswith(f"{prefix} ") for prefix in SAFE_PREFIXES)
