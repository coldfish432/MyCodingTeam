from __future__ import annotations

import shlex
from pathlib import PurePosixPath, PureWindowsPath

from my_coding_team.runtime.agentscope_adapter import (
    PermissionBehavior,
    PermissionRule,
)
from my_coding_team.schemas.task import TaskContract


READONLY_BASH_PREFIXES = [
    "git status:*",
    "git log:*",
    "git diff:*",
    "git show:*",
    "git branch:*",
    "git rev-parse:*",
    "ls:*",
    "cat:*",
    "head:*",
    "tail:*",
    "wc:*",
    "find:*",
    "rg:*",
    "tree:*",
    "pwd:*",
    "file:*",
]


DESTRUCTIVE_BASH_PREFIXES = [
    "rm:*",
    "rmdir:*",
    "mv:*",
    "dd:*",
    "shred:*",
    "chmod:*",
    "chown:*",
    "git checkout:*",
    "git reset:*",
    "git clean:*",
    "git rebase:*",
    "git push:*",
    "git merge:*",
    "git commit:*",
    "git branch -D:*",
    "sudo:*",
    "curl:*",
    "wget:*",
]


def allow(tool_name: str, pattern: str, source: str = "readonly_probe") -> PermissionRule:
    """构建允许规则。

    参数：
        tool_name: AgentScope 工具名。
        pattern: 工具规则内容，例如文件 glob 或 Bash 前缀。
        source: 规则来源标识。

    返回：
        behavior=ALLOW 的 PermissionRule。
    """
    return PermissionRule(
        tool_name=tool_name,
        rule_content=pattern,
        behavior=PermissionBehavior.ALLOW,
        source=source,
    )


def deny(tool_name: str, pattern: str, source: str = "readonly_probe") -> PermissionRule:
    """构建拒绝规则。

    参数：
        tool_name: AgentScope 工具名。
        pattern: 工具规则内容，例如危险 Bash 前缀。
        source: 规则来源标识。

    返回：
        behavior=DENY 的 PermissionRule。
    """
    return PermissionRule(
        tool_name=tool_name,
        rule_content=pattern,
        behavior=PermissionBehavior.DENY,
        source=source,
    )


def build_readonly_probe_rules() -> dict[str, list[PermissionRule]]:
    """构建只读 probe Agent 的 allow_rules。

    参数：
        无。

    返回：
        允许 Read/Grep/Glob 和只读 Bash 前缀的规则字典。

    Pair this with build_readonly_probe_deny_rules() when the agent runs in
    DONT_ASK; otherwise destructive commands surface as RequireUserConfirmEvent
    instead of a hard denial.
    """
    return {
        "Read": [allow("Read", "**")],
        "Grep": [allow("Grep", "**")],
        "Glob": [allow("Glob", "**")],
        "Bash": [allow("Bash", prefix) for prefix in READONLY_BASH_PREFIXES],
    }


def build_readonly_probe_deny_rules() -> dict[str, list[PermissionRule]]:
    """构建只读 probe Agent 的 destructive deny_rules。

    参数：
        无。

    返回：
        明确拒绝 destructive Bash 前缀的规则字典。

    AgentScope 2.0.0's built-in safety layer raises RequireUserConfirmEvent
    for destructive commands such as `rm -rf` even when they are not in
    allow_rules. In unattended modes (DONT_ASK), an explicit DENY rule is
    required to preempt the confirmation event and hard-block the call.
    """
    return {
        "Bash": [deny("Bash", prefix) for prefix in DESTRUCTIVE_BASH_PREFIXES],
    }


def to_bash_prefix(command: str) -> str | None:
    """把具体 shell 命令转换为 AgentScope Bash allow 前缀。

    参数：
        command: 具体命令，例如 `pytest tests/test_x.py`。

    返回：
        Bash 权限前缀；空命令返回 None。
    """
    tokens = _split_command(command)
    if not tokens:
        return None

    head = tokens[0]
    if len(tokens) >= 2 and head in {"git", "npm", "pnpm", "yarn"}:
        return f"{head} {tokens[1]}:*"
    if len(tokens) >= 2 and head in {"python", "python3", "py"} and tokens[1] == "-m":
        return f"{head} -m:*"
    return f"{head}:*"


def build_task_allow_rules(
    contract: TaskContract,
    *,
    source: str = "task_contract",
) -> dict[str, list[PermissionRule]]:
    """根据 TaskContract 构建实现/验证 Agent 的 allow_rules。

    参数：
        contract: 单任务合同，提供 allowed_files 和 verification_commands。
        source: 写入 PermissionRule.source 的来源标识。

    返回：
        包含 Read/Grep/Glob、Write/Edit 和可选 Bash 规则的字典。

    异常：
        ValueError: allowed_files 中包含空路径、绝对路径或父级穿越。

    File patterns are intentionally repository-relative. Absolute paths and
    parent traversal are rejected before rules reach AgentScope.
    """
    file_patterns = [_normalize_allowed_file_pattern(path) for path in contract.allowed_files]
    bash_patterns = [
        prefix
        for command in contract.verification_commands
        if (prefix := to_bash_prefix(command)) is not None
    ]

    rules: dict[str, list[PermissionRule]] = {
        "Read": [allow("Read", "**", source)],
        "Grep": [allow("Grep", "**", source)],
        "Glob": [allow("Glob", "**", source)],
        "Write": [allow("Write", pattern, source) for pattern in file_patterns],
        "Edit": [allow("Edit", pattern, source) for pattern in file_patterns],
    }
    if bash_patterns:
        rules["Bash"] = [allow("Bash", pattern, source) for pattern in bash_patterns]
    return _dedupe_rules(rules)


def _split_command(command: str) -> list[str]:
    """拆分 shell 命令为 token。

    参数：
        command: 原始命令字符串。

    返回：
        token 列表；空命令返回空列表。
    """
    stripped = command.strip()
    if not stripped:
        return []
    try:
        return shlex.split(stripped, posix=False)
    except ValueError:
        return stripped.split()


def _normalize_allowed_file_pattern(path: str) -> str:
    """规范化并校验 allowed_files 路径模式。

    参数：
        path: 合同中的路径或目录模式。

    返回：
        统一为 POSIX 风格的相对路径模式。
    """
    value = path.strip().replace("\\", "/")
    if not value:
        raise ValueError("allowed file pattern must not be empty")
    if _is_absolute_path(value):
        raise ValueError(f"allowed file pattern must be repository-relative: {path}")

    parts = PurePosixPath(value).parts
    if any(part == ".." for part in parts):
        raise ValueError(f"allowed file pattern must not contain parent traversal: {path}")
    if parts and parts[0] in {"~", "$HOME", "%USERPROFILE%"}:
        raise ValueError(f"allowed file pattern must not target a home directory: {path}")

    is_directory_pattern = value.endswith("/")
    normalized = PurePosixPath(value).as_posix()
    if is_directory_pattern:
        return f"{normalized}/**"
    return normalized


def _is_absolute_path(path: str) -> bool:
    """同时识别 POSIX 和 Windows 绝对路径。"""
    return PurePosixPath(path).is_absolute() or PureWindowsPath(path).is_absolute()


def _dedupe_rules(rules: dict[str, list[PermissionRule]]) -> dict[str, list[PermissionRule]]:
    """按工具名、规则内容和行为去重 PermissionRule。"""
    deduped: dict[str, list[PermissionRule]] = {}
    seen: set[tuple[str, str, PermissionBehavior]] = set()
    for tool_name, tool_rules in rules.items():
        for rule in tool_rules:
            key = (rule.tool_name, rule.rule_content, rule.behavior)
            if key in seen:
                continue
            seen.add(key)
            deduped.setdefault(tool_name, []).append(rule)
    return deduped
