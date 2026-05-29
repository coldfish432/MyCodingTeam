"""Single-task and multi-task planning steps."""

from __future__ import annotations

import json

from my_coding_team.core.registry import register_step
from my_coding_team.core.step import LLMBackedStep, StepContext
from my_coding_team.runtime.middleware import dumps_for_prompt, parse_schema
from my_coding_team.runtime.prompts import load_prompt
from my_coding_team.schemas.common import Evidence
from my_coding_team.schemas.step_inputs import PlanningQueueInput, PlanningSingleInput
from my_coding_team.schemas.task import TaskContract, TaskItem, TaskQueue
from my_coding_team.schemas.workflow import ProductBrief, RepoContext


SAFE_VERIFICATION_PREFIXES = (
    "pytest",
    "python -m pytest",
    "py -m pytest",
    "python -m my_coding_team doctor",
)


class PlanningSingleStep(LLMBackedStep[PlanningSingleInput, TaskContract]):
    name = "planning_single"
    input_schema = PlanningSingleInput
    output_schema = TaskContract

    def build_prompt_input(self, input: PlanningSingleInput) -> str:
        repo_context = RepoContext.model_validate(input.repo_context)
        return (
            f"{load_prompt('planning')}\n\n"
            f"Request:\n{input.request}\n\n"
            f"Workspace:\n{input.workspace.model_dump_json(indent=2)}\n\n"
            f"Repo context:\n{repo_context.model_dump_json(indent=2)}"
        )

    def make_agent(self, context: StepContext):
        return context.model

    async def run(self, input: PlanningSingleInput, context: StepContext) -> TaskContract:
        repo_context = RepoContext.model_validate(input.repo_context)
        if context.model is None:
            return _fallback_contract(input.request, repo_context)
        payload = await context.model.complete_json(self.build_prompt_input(input))
        context.llm_call_charge += 1
        contract = parse_schema(TaskContract, payload)
        if not contract.verification_commands:
            raise ValueError("TaskContract.verification_commands cannot be empty in MVP")
        contract.verification_commands = _safe_verification_commands(
            contract.verification_commands,
            repo_context,
        )
        return contract


class PlanningQueueStep(LLMBackedStep[PlanningQueueInput, TaskQueue]):
    name = "planning_queue"
    input_schema = PlanningQueueInput
    output_schema = TaskQueue

    def build_prompt_input(self, input: PlanningQueueInput) -> str:
        brief = ProductBrief.model_validate(input.brief)
        repo_context = RepoContext.model_validate(input.repo_context)
        return (
            f"{load_prompt('planning')}\n\n"
            f"ProductBrief:\n{dumps_for_prompt(brief)}\n\n"
            f"Repo context:\n{repo_context.model_dump_json(indent=2)}\n\n"
            "Output a TaskQueue with the items array."
        )

    def make_agent(self, context: StepContext):
        return context.model

    async def run(self, input: PlanningQueueInput, context: StepContext) -> TaskQueue:
        brief = ProductBrief.model_validate(input.brief)
        repo_context = RepoContext.model_validate(input.repo_context)
        if context.model is None:
            return _fallback_queue(brief, repo_context)
        payload = await context.model.complete_json(self.build_prompt_input(input))
        context.llm_call_charge += 1
        try:
            return parse_schema(TaskQueue, payload)
        except Exception:
            return _repair_queue(payload, brief, repo_context)


PLANNING_SINGLE = register_step(PlanningSingleStep())
PLANNING_QUEUE = register_step(PlanningQueueStep())


def _repair_queue(payload: str | dict, brief: ProductBrief, repo_context: RepoContext) -> TaskQueue:
    """Strip TaskContract-only fields when a model mixes them into TaskItem."""
    item_keys = {"task_id", "title", "description", "files", "depends_on", "risk", "status"}

    try:
        data = json.loads(payload) if isinstance(payload, str) else dict(payload)
    except Exception:
        return _fallback_queue(brief, repo_context)

    items = data.get("items", [])
    cleaned_items: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        cleaned_items.append({k: v for k, v in item.items() if k in item_keys})

    data["items"] = cleaned_items

    try:
        return parse_schema(TaskQueue, data)
    except Exception:
        return _fallback_queue(brief, repo_context)


def _fallback_queue(brief: ProductBrief, repo_context: RepoContext) -> TaskQueue:
    """Generate a conservative one-item queue without a model."""
    target = "README.md"
    if repo_context.relevant_files:
        py_files = [path for path in repo_context.relevant_files if path.endswith(".py")]
        md_files = [path for path in repo_context.relevant_files if path.endswith(".md")]
        target = py_files[0] if py_files else (md_files[0] if md_files else repo_context.relevant_files[0])

    return TaskQueue(
        items=[
            TaskItem(
                task_id="T1",
                title=brief.title,
                description=brief.summary,
                files=[target],
                risk="low",
            )
        ],
        strategy="sequential",
        estimated_total_calls=5,
    )


def _fallback_contract(request: str, repo_context: RepoContext) -> TaskContract:
    """Generate a conservative single-file contract without a model."""
    target = "README.md"
    if repo_context.relevant_files:
        md_files = [path for path in repo_context.relevant_files if path.endswith(".md")]
        target = md_files[0] if md_files else repo_context.relevant_files[0]
    command = "python -m pytest" if repo_context.test_entrypoints else "python -m my_coding_team doctor"
    return TaskContract(
        task_id="T1",
        goal=request,
        allowed_files=[target],
        verification_commands=[command],
        evidence=[Evidence(path=target, note="selected by fallback planner")],
    )


def _safe_verification_commands(commands: list[str], repo_context: RepoContext) -> list[str]:
    """Restrict model-produced verification commands to the MVP allowlist."""
    safe = [command for command in commands if _is_safe_verification_command(command)]
    if safe:
        return safe
    return ["python -m pytest"] if repo_context.test_entrypoints else ["python -m my_coding_team doctor"]


def _is_safe_verification_command(command: str) -> bool:
    """Return whether a planning verification command is in the allowlist."""
    normalized = " ".join(command.strip().split())
    return any(
        normalized == prefix or normalized.startswith(f"{prefix} ")
        for prefix in SAFE_VERIFICATION_PREFIXES
    )
