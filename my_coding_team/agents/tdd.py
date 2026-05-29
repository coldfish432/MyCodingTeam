"""TDD RED stage for Phase 8a."""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path
from typing import Any

from my_coding_team.orchestration.permission_builder import (
    build_readonly_probe_deny_rules,
    build_tdd_permission_rules,
)
from my_coding_team.runtime.prompts import load_prompt
from my_coding_team.schemas.common import Evidence
from my_coding_team.schemas.task import RedResult, TaskContract


def make_tdd_agent(contract: TaskContract, workspace, model):
    """Build an AgentScope TDD agent for future tool-driven RED flows."""
    from my_coding_team.runtime.agentscope_adapter import Bash, Edit, Glob, Grep, PermissionMode, Read, Write
    from my_coding_team.runtime.factory import create_agent

    return create_agent(
        name=f"TDD-{contract.task_id}",
        system_prompt=_format_tdd_prompt(contract),
        model=model,
        tools=[Read(), Grep(), Glob(), Write(), Edit(), Bash()],
        permission_mode=PermissionMode.DONT_ASK,
        allow_rules=build_tdd_permission_rules(contract),
        deny_rules=build_readonly_probe_deny_rules(),
        offloader=workspace,
    )


async def run_tdd_red(
    contract: TaskContract,
    workspace_root: str | Path,
    model,
    *,
    timeout_seconds: int = 60,
) -> RedResult:
    """Ask the model for RED test changes, apply them, then run the RED command."""
    if model is None:
        return RedResult(task_id=contract.task_id, red_type="skip", skip_reason="No model supplied for RED")

    prompt = (
        f"{_format_tdd_prompt(contract)}\n\n"
        f"Contract:\n{contract.model_dump_json(indent=2)}"
    )
    payload = await model.complete_json(prompt)
    changes = payload.get("changes", [])
    changed_files = _apply_red_changes(Path(workspace_root), contract.red_allowed_files, changes)
    command = _red_command(contract)
    output, exit_code = _run_red_command(command, Path(workspace_root), timeout_seconds=timeout_seconds)
    return RedResult(
        task_id=contract.task_id,
        red_type="test",
        files_changed=changed_files,
        command=command,
        expected_failure_signature=payload.get("expected_failure_signature"),
        actual_output=output,
        failed_for_expected_reason=exit_code != 0,
        failure_category=payload.get("failure_category"),
        failure_excerpt=payload.get("failure_excerpt"),
        evidence=[Evidence(path=changed_files[0] if changed_files else ".", note="RED test output")],
    )


def _format_tdd_prompt(contract: TaskContract) -> str:
    return load_prompt("tdd").format(
        red_allowed_files=", ".join(contract.red_allowed_files),
        red_verification_command=contract.red_verification_command or _red_command(contract),
        hints="\n".join(f"- {hint}" for hint in contract.expected_failure_signature_hints) or "(none)",
    )


def _red_command(contract: TaskContract) -> str:
    return contract.red_verification_command or (contract.verification_commands[0] if contract.verification_commands else "")


def _run_red_command(command: str, root: Path, *, timeout_seconds: int) -> tuple[str, int]:
    if not command:
        return "not_run missing red_verification_command", 1
    result = subprocess.run(
        command,
        cwd=root,
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )
    output = (result.stdout + "\n" + result.stderr).strip()
    return f"$ {command}\nexit={result.returncode}\n{output[-2000:]}", result.returncode


def _apply_red_changes(root: Path, allowed_files: list[str], changes: list[dict[str, Any]]) -> list[str]:
    prepared: list[tuple[str, str]] = []
    for change in changes:
        rel_path = str(change.get("path", "")).replace("\\", "/").strip()
        if not rel_path or rel_path.startswith("../") or Path(rel_path).is_absolute():
            raise PermissionError(f"Refusing unsafe RED path: {rel_path}")
        if not _is_allowed(rel_path, allowed_files):
            raise PermissionError(f"RED path is outside red_allowed_files: {rel_path}")
        prepared.append((rel_path, str(change.get("content", ""))))

    changed: list[str] = []
    for rel_path, content in prepared:
        target = root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        changed.append(rel_path)
    return changed


def _is_allowed(path: str, allowed_files: list[str]) -> bool:
    for pattern in allowed_files:
        normalized = pattern.replace("\\", "/")
        if normalized.endswith("/"):
            normalized = f"{normalized}**"
        if fnmatch.fnmatch(path, normalized):
            return True
    return False
