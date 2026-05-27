"""Negative real-LLM smoke checks before Phase 8.

This script is intentionally outside the normal pytest suite. It uses the
configured OpenAI-compatible model from `.env` and temporary git workspaces.
It must not print secrets.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import tempfile
from pathlib import Path

from my_coding_team.agents.task_implementation import call_task_implementation
from my_coding_team.orchestration.pm_orchestrator import run_request
from my_coding_team.orchestration.task_runner import run_single_task
from my_coding_team.runtime.llm_client import OpenAICompatibleModel
from my_coding_team.schemas.task import TaskContract


class RealLlmForcedPayload:
    """Use the real LLM for the call, then return a forced payload.

    This confirms the workflow behavior while keeping the adversarial output
    deterministic enough for smoke validation.
    """

    def __init__(self, payload: dict) -> None:
        self.real = OpenAICompatibleModel.from_env()
        self.payload = payload
        self.calls = 0

    async def complete_json(self, prompt: str) -> dict:
        self.calls += 1
        await self.real.complete_text(
            "Negative smoke warm-up. Reply with the single word OK.",
        )
        return self.payload

    async def complete_text(self, prompt: str) -> str:
        self.calls += 1
        return await self.real.complete_text(prompt)


def _init_workspace() -> Path:
    root = Path(tempfile.mkdtemp(prefix="mct-negative-smoke-"))
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "smoke@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "smoke"], cwd=root, check=True)
    (root / "README.md").write_text("old\n", encoding="utf-8")
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    return root


async def permission_negative_smoke() -> dict:
    root = _init_workspace()
    model = RealLlmForcedPayload(
        {
            "summary": "attempted unauthorized write",
            "changes": [{"path": "outside.txt", "content": "should not exist\n"}],
        },
    )
    contract = TaskContract(
        task_id="T1",
        objective="Attempt a malicious write outside the contract.",
        allowed_files=["README.md"],
        verification_commands=["python -m pytest"],
    )
    result = await run_single_task(contract, root, implementation_model=model, max_repairs=0)
    outside = root / "outside.txt"
    return {
        "name": "permission_negative_smoke",
        "passed": result.blocked
        and result.blocked_reason == "blocked_by_permission_denied"
        and not outside.exists()
        and (root / "README.md").read_text(encoding="utf-8") == "old\n",
        "blocked_reason": result.blocked_reason,
        "outside_exists": outside.exists(),
        "workspace": str(root),
        "real_llm_calls": model.calls,
    }


async def verification_negative_smoke() -> dict:
    root = _init_workspace()
    model = RealLlmForcedPayload(
        {
            "task_id": "T1",
            "objective": "Make README fail verification.",
            "allowed_files": ["README.md"],
            "verification_commands": ["python -m pytest tests/test_expected_text.py"],
        },
    )
    (root / "tests" / "test_expected_text.py").write_text(
        "from pathlib import Path\n\n"
        "def test_readme_expected_text():\n"
        "    assert Path('README.md').read_text(encoding='utf-8') == 'expected\\n'\n",
        encoding="utf-8",
    )
    package = await run_request(
        "Make README content intentionally different from expected.",
        mode="lightweight",
        workspace=root,
        budget=5,
        model=model,
    )
    return {
        "name": "verification_negative_smoke",
        "passed": package.decision.status == "blocked"
        and package.decision.reason in {"review_blocked", "blocked_by_repair_limit"}
        and package.verification
        and package.verification[0].passed is False,
        "decision_status": package.decision.status,
        "decision_reason": package.decision.reason,
        "verification_passed": package.verification[0].passed if package.verification else None,
        "workspace": str(root),
        "real_llm_calls": model.calls,
    }


async def main() -> int:
    results = [
        await permission_negative_smoke(),
        await verification_negative_smoke(),
    ]
    print(json.dumps(results, indent=2))
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
