"""Single-task planning for Phase 7 MVP."""

from __future__ import annotations

from my_coding_team.runtime.middleware import dumps_for_prompt, parse_schema
from my_coding_team.runtime.prompts import load_prompt
from my_coding_team.schemas.common import Evidence
from my_coding_team.schemas.task import TaskContract
from my_coding_team.schemas.workflow import RepoContext, WorkspaceRecord


SAFE_VERIFICATION_PREFIXES = (
    "pytest",
    "python -m pytest",
    "py -m pytest",
    "python -m my_coding_team doctor",
)


async def call_planning_for_single_contract(
    request: str,
    repo_context: RepoContext,
    workspace: WorkspaceRecord,
    model=None,
) -> TaskContract:
    """生成 Phase 7 MVP 的单任务 TaskContract。

    参数：
        request: 用户原始请求。
        repo_context: Context Scout 收集的仓库上下文。
        workspace: Workspace Manager 生成的工作区记录。
        model: 可选真实或 mock 模型；为空时使用保守 fallback contract。

    返回：
        包含 allowed_files 和 verification_commands 的 TaskContract。

    异常：
        ValueError: 模型生成的合同缺少 MVP 必需的验证命令。
    """
    if model is None:
        return _fallback_contract(request, repo_context)
    prompt = (
        f"{load_prompt('planning')}\n\n"
        f"Request:\n{request}\n\n"
        f"Workspace:\n{workspace.model_dump_json(indent=2)}\n\n"
        f"Repo context:\n{repo_context.model_dump_json(indent=2)}"
    )
    payload = await model.complete_json(prompt)
    contract = parse_schema(TaskContract, payload)
    if not contract.verification_commands:
        raise ValueError("TaskContract.verification_commands cannot be empty in MVP")
    contract.verification_commands = _safe_verification_commands(
        contract.verification_commands,
        repo_context,
    )
    return contract


def _fallback_contract(request: str, repo_context: RepoContext) -> TaskContract:
    """在没有模型时生成保守的单文件合同。

    参数：
        request: 用户原始请求。
        repo_context: Context Scout 输出。

    返回：
        指向一个候选文件且带验证命令的 TaskContract。
    """
    target = "README.md"
    if repo_context.relevant_files:
        # 文档任务优先落到 Markdown；否则选第一个相关文件，避免无边界改动。
        md_files = [path for path in repo_context.relevant_files if path.endswith(".md")]
        target = md_files[0] if md_files else repo_context.relevant_files[0]
    command = "python -m pytest" if repo_context.test_entrypoints else "python -m my_coding_team doctor"
    return TaskContract(
        task_id="T1",
        objective=request,
        allowed_files=[target],
        verification_commands=[command],
        evidence=[Evidence(path=target, note="selected by fallback planner")],
    )


def _safe_verification_commands(commands: list[str], repo_context: RepoContext) -> list[str]:
    """把模型生成的验证命令收敛到 MVP 安全白名单。

    参数：
        commands: 模型生成的验证命令。
        repo_context: Context Scout 输出，用于选择安全兜底命令。

    返回：
        安全验证命令列表；全部不安全时返回确定性 fallback。
    """
    safe = [command for command in commands if _is_safe_verification_command(command)]
    if safe:
        return safe
    return ["python -m pytest"] if repo_context.test_entrypoints else ["python -m my_coding_team doctor"]


def _is_safe_verification_command(command: str) -> bool:
    """判断 planning 输出的验证命令是否满足 MVP 安全白名单。"""
    normalized = " ".join(command.strip().split())
    return any(
        normalized == prefix or normalized.startswith(f"{prefix} ")
        for prefix in SAFE_VERIFICATION_PREFIXES
    )
