"""Verification runner step for task and final scopes."""

from __future__ import annotations

import subprocess
from pathlib import Path

from my_coding_team.core.registry import register_step
from my_coding_team.core.step import LLMBackedStep, StepContext
from my_coding_team.schemas.common import Evidence
from my_coding_team.schemas.step_inputs import QAVerificationInput
from my_coding_team.schemas.task import TaskContract, TaskRepairContract, VerificationResult


SAFE_PREFIXES = (
    "pytest",
    "python -m pytest",
    "py -m pytest",
    "python -m my_coding_team doctor",
)


class QAVerificationStep(LLMBackedStep[QAVerificationInput, VerificationResult]):
    name = "qa_verification"
    input_schema = QAVerificationInput
    output_schema = VerificationResult

    def build_prompt_input(self, input: QAVerificationInput) -> str:
        return input.model_dump_json(indent=2)

    def make_agent(self, context: StepContext):
        return context.model

    async def run(self, input: QAVerificationInput, context: StepContext) -> VerificationResult:
        contract = None
        if input.contract is not None:
            if "original_task_id" in input.contract:
                contract = TaskRepairContract.model_validate(input.contract)
            else:
                contract = TaskContract.model_validate(input.contract)

        if input.scope == "final" and input.commands is not None:
            verification_commands = list(input.commands)
            task_id = "final"
        elif contract is not None:
            verification_commands = list(contract.verification_commands)
            task_id = getattr(contract, "task_id", getattr(contract, "original_task_id", "repair"))
        else:
            return VerificationResult(
                task_id="unknown",
                passed=False,
                commands=[],
                failed_commands=[],
                output_summary="no contract or commands provided",
                evidence=[Evidence(path=".", note="no verification input")],
            )

        workspace_root = Path(input.workspace_root or Path.cwd())

        failed: list[str] = []
        summaries: list[str] = []
        for command in verification_commands:
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
                timeout=input.timeout_seconds,
            )
            output = (result.stdout + "\n" + result.stderr).strip()
            summaries.append(f"$ {command}\nexit={result.returncode}\n{output[-1200:]}")
            if result.returncode != 0:
                failed.append(command)
        passed = bool(verification_commands) and not failed
        return VerificationResult(
            task_id=task_id,
            passed=passed,
            commands=verification_commands,
            failed_commands=failed,
            output_summary="\n\n".join(summaries),
            evidence=[Evidence(path=".", note=f"{input.scope} verification")],
        )


QA_VERIFICATION = register_step(QAVerificationStep())


def _is_safe_command(command: str) -> bool:
    """Return whether a verification command is in the allowlist."""
    normalized = " ".join(command.strip().split())
    return any(normalized == prefix or normalized.startswith(f"{prefix} ") for prefix in SAFE_PREFIXES)
