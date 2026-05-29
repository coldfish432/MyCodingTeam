"""Repository context scout step."""

from __future__ import annotations

from pathlib import Path

from my_coding_team.core.registry import register_step
from my_coding_team.core.step import LLMBackedStep, StepContext
from my_coding_team.orchestration.permission_builder import (
    build_readonly_probe_deny_rules,
    build_readonly_probe_rules,
)
from my_coding_team.runtime.prompts import load_prompt
from my_coding_team.schemas.common import Evidence
from my_coding_team.schemas.step_inputs import ContextScoutInput
from my_coding_team.schemas.workflow import RepoContext, WorkspaceRecord


def make_context_scout_agent(model):
    """Build the ContextScout Agent with read-only probe tools."""
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


class ContextScoutStep(LLMBackedStep[ContextScoutInput, RepoContext]):
    name = "context_scout"
    input_schema = ContextScoutInput
    output_schema = RepoContext

    def build_prompt_input(self, input: ContextScoutInput) -> str:
        return f"{load_prompt('context_scout')}\n\nRequest:\n{input.request}\n\nWorkspace:\n{input.workspace.model_dump_json(indent=2)}"

    def make_agent(self, context: StepContext):
        return make_context_scout_agent(context.model)

    async def run(self, input: ContextScoutInput, context: StepContext) -> RepoContext:
        # Phase 10.5 preserves the existing deterministic scout behavior.
        root = Path(input.workspace.root)
        files = _candidate_files(root)
        tests = [path for path in files if path.startswith("tests/") and path.endswith(".py")]
        build_commands = ["python -m pytest"] if tests else []
        evidence = [Evidence(path=files[0], note="first relevant file")] if files else []
        risks = ["workspace has uncommitted changes"] if input.workspace.dirty_files else []
        return RepoContext(
            relevant_files=files[:20],
            test_entrypoints=tests[:10],
            build_commands=build_commands,
            risks=risks,
            evidence=evidence,
        )


CONTEXT_SCOUT = register_step(ContextScoutStep())


def _candidate_files(root: Path) -> list[str]:
    """Scan source and docs files suitable for repository context."""
    ignored = {".git", ".venv", ".pip-cache", ".pytest_cache", "__pycache__"}
    results: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in ignored for part in path.parts):
            continue
        if path.suffix.lower() in {".py", ".md", ".toml"}:
            results.append(path.relative_to(root).as_posix())
    return sorted(results)
