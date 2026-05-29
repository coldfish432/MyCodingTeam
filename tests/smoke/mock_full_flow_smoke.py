"""Mock smoke proof for Phase 9 orchestration.

This test does not validate real LLM prompt quality. It proves that when each
agent returns valid structured outputs, Full Product Flow can chain Shape,
Specification, Signoff, TaskQueue execution, final verification, final review,
and delivery.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from my_coding_team.orchestration.pm_orchestrator import run_request
from my_coding_team.schemas.common import Evidence
from my_coding_team.schemas.room_inputs import TDDRoomOutput
from my_coding_team.schemas.review import FinalReviewReport, TaskReviewResult
from my_coding_team.schemas.task import (
    ImplementationResult,
    RedResult,
    TaskContract,
    TaskQueue,
    TaskItem,
    VerificationResult,
)
from my_coding_team.schemas.workflow import (
    DesignSignoff,
    ProblemFrame,
    ProductBrief,
    RepoContext,
)


def _prepare_calc_workspace(root: Path) -> Path:
    workspace = root / "calc_project"
    (workspace / "src").mkdir(parents=True)
    (workspace / "tests").mkdir()
    (workspace / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "calc"
version = "0.1.0"
""",
        encoding="utf-8",
    )
    (workspace / "src" / "__init__.py").write_text("", encoding="utf-8")
    (workspace / "src" / "calc.py").write_text(
        '''"""Simple calculator module."""

def multiply(a, b):
    return a * b
''',
        encoding="utf-8",
    )
    (workspace / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (workspace / "tests" / "test_calc.py").write_text(
        """from src.calc import multiply

def test_multiply():
    assert multiply(2, 3) == 6
""",
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=workspace, capture_output=True, check=False)
    subprocess.run(["git", "config", "user.email", "smoke@test.local"], cwd=workspace, capture_output=True, check=False)
    subprocess.run(["git", "config", "user.name", "Smoke Test"], cwd=workspace, capture_output=True, check=False)
    subprocess.run(["git", "add", "-A"], cwd=workspace, capture_output=True, check=False)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=workspace, capture_output=True, check=False)
    return workspace


@pytest.mark.asyncio
async def test_full_flow_with_perfect_mock_responses(tmp_path, monkeypatch):
    """Valid agent outputs should let the Phase 9 orchestrator reach delivery."""

    import my_coding_team.workflows.full_product as full_product
    import my_coding_team.orchestration.task_runner as task_runner

    workspace = _prepare_calc_workspace(tmp_path)

    async def fake_shape(request, route=None, model=None):
        return ProblemFrame(
            user_request=request,
            problem="Add a CLI to the calc project.",
            goals=["Add CLI", "Add tests", "Update docs"],
            constraints=["Use existing src package layout"],
            candidate_directions=["Argparse CLI", "Click CLI"],
            recommended_direction="Argparse CLI",
            evidence=[Evidence(path="src/calc.py", note="Repo exposes multiply only in fixture")],
        )

    async def fake_specification(frame, model=None):
        return ProductBrief(
            title="Calc CLI",
            summary="Add a calc-cli command, tests, and README usage.",
            goals=["Create CLI", "Cover CLI with tests", "Document usage"],
            non_goals=["Do not validate real LLM prompt quality"],
            requirements=["Create src/cli.py", "Create tests/test_cli.py", "Update README.md"],
            acceptance_criteria=["All mocked task verification results pass"],
            assumptions=["Repo facts come from Context Scout"],
            evidence=[Evidence(path="src/calc.py", note="Existing calculator module")],
        )

    def fake_signoff(brief):
        return DesignSignoff(
            permission_to_plan=True,
            approved_by="mock",
            reason="mock_approved",
            approved_direction=brief.title,
            approved_scope=list(brief.goals),
        )

    async def fake_context_scout(request, workspace_record, model=None):
        return RepoContext(
            relevant_files=["src/calc.py", "pyproject.toml", "tests/test_calc.py"],
            test_entrypoints=["tests"],
            build_commands=["python -m pytest"],
            evidence=[Evidence(path="src/calc.py", note="mock repo context")],
        )

    async def fake_planning_queue(brief, repo_context, model=None):
        return TaskQueue(
            items=[
                TaskItem(task_id="T1", title="Create CLI", files=["src/cli.py"]),
                TaskItem(task_id="T2", title="Create CLI tests", files=["tests/test_cli.py"]),
                TaskItem(task_id="T3", title="Update README", files=["README.md"]),
            ],
            strategy="sequential",
            estimated_total_calls=3,
        )

    async def fake_tdd(contract, workspace_root, model=None):
        return RedResult(
            task_id=contract.task_id,
            red_type="test",
            files_changed=[f"tests/test_{contract.task_id.lower()}_red.py"],
            command=contract.red_verification_command or "python -m pytest",
            expected_failure_signature="ModuleNotFoundError",
            actual_output="ModuleNotFoundError: missing implementation",
            failed_for_expected_reason=True,
            failure_category="import_error",
            failure_excerpt="ModuleNotFoundError",
        )

    async def fake_implementation(contract, workspace_root, model=None):
        root = Path(workspace_root)
        changed_files = []
        for path in contract.allowed_files:
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if path == "src/cli.py":
                target.write_text("def main():\n    print('8')\n", encoding="utf-8")
            elif path == "tests/test_cli.py":
                target.write_text("def test_cli():\n    assert True\n", encoding="utf-8")
            elif path == "README.md":
                target.write_text("# Calc\n\n## CLI Usage\n\n`calc-cli add 3 5`\n", encoding="utf-8")
            else:
                target.write_text("# mock change\n", encoding="utf-8")
            changed_files.append(path)
        return ImplementationResult(
            task_id=getattr(contract, "task_id", getattr(contract, "original_task_id", "repair")),
            success=True,
            summary="mock implementation complete",
            changed_files=changed_files,
        )

    async def fake_task_verification(contract, workspace_root, *args, **kwargs):
        task_id = getattr(contract, "task_id", getattr(contract, "original_task_id", "final"))
        return VerificationResult(
            task_id=task_id,
            passed=True,
            commands=["python -m pytest"],
            output_summary="mock verification passed",
        )

    async def fake_final_verification(contract=None, workspace_root=None, *args, **kwargs):
        if kwargs.get("scope") == "final":
            return VerificationResult(
                task_id="final",
                passed=True,
                commands=kwargs.get("commands", ["python -m pytest"]),
                output_summary="mock final verification passed",
            )
        return await fake_task_verification(contract, workspace_root, *args, **kwargs)

    async def fake_task_review(contract, implementation, verification, *args, **kwargs):
        return TaskReviewResult(
            task_id=contract.task_id,
            approval=True,
            summary="mock task review approved",
        )

    async def fake_review_room(*args, **kwargs):
        if kwargs.get("scope") == "final":
            return FinalReviewReport(
                approval=True,
                summary="mock final review approved",
                findings=[],
            )
        return await fake_task_review(*args, **kwargs)

    class FakeShapeStep:
        async def run(self, input, context):
            return await fake_shape(input.request, route=input.route, model=context.model)

    class FakeSpecificationStep:
        async def run(self, input, context):
            frame = ProblemFrame.model_validate(input.problem_frame)
            return await fake_specification(frame, model=context.model)

    class FakeContextScoutStep:
        async def run(self, input, context):
            return await fake_context_scout(input.request, input.workspace, model=context.model)

    class FakePlanningQueueStep:
        async def run(self, input, context):
            brief = ProductBrief.model_validate(input.brief)
            repo_context = RepoContext.model_validate(input.repo_context)
            return await fake_planning_queue(brief, repo_context, model=context.model)

    class FakeQAStep:
        async def run(self, input, context):
            if input.scope == "final":
                return await fake_final_verification(
                    workspace_root=input.workspace_root,
                    scope="final",
                    commands=input.commands,
                )
            contract = TaskContract.model_validate(input.contract)
            return await fake_task_verification(contract, input.workspace_root)

    class FakeTDDRoom:
        async def execute(self, input, context):
            contract = TaskContract.model_validate(input.contract)
            red = await fake_tdd(contract, input.workspace_root, model=context.model)
            return TDDRoomOutput(red_result=red.model_dump(), verified=True)

    class FakeImplementationRoom:
        async def execute(self, input, context):
            contract = TaskContract.model_validate(input.contract)
            return await fake_implementation(contract, input.workspace_root, model=context.model)

    class FakeReviewRoom:
        async def execute(self, input, context):
            if input.scope == "final":
                return FinalReviewReport(
                    approval=True,
                    summary="mock final review approved",
                    findings=[],
                )
            return await fake_task_review(
                TaskContract.model_validate(input.contract),
                ImplementationResult.model_validate(input.implementation),
                VerificationResult.model_validate(input.verification),
            )

    monkeypatch.setitem(full_product.STEPS, "shape", FakeShapeStep())
    monkeypatch.setitem(full_product.STEPS, "specification", FakeSpecificationStep())
    monkeypatch.setattr(full_product, "request_design_signoff_cli", fake_signoff)
    monkeypatch.setitem(full_product.STEPS, "context_scout", FakeContextScoutStep())
    monkeypatch.setitem(full_product.STEPS, "planning_queue", FakePlanningQueueStep())
    monkeypatch.setitem(full_product.STEPS, "qa_verification", FakeQAStep())
    monkeypatch.setitem(task_runner.STEPS, "qa_verification", FakeQAStep())
    monkeypatch.setitem(task_runner.ROOMS, "tdd_room", FakeTDDRoom())
    monkeypatch.setitem(task_runner.ROOMS, "implementation_room", FakeImplementationRoom())
    monkeypatch.setitem(task_runner.ROOMS, "review_room", FakeReviewRoom())
    monkeypatch.setitem(full_product.ROOMS, "review_room", FakeReviewRoom())

    package = await run_request(
        "Add calc-cli, tests, and README usage.",
        budget=50,
        workspace=workspace,
        mode="full",
        model=object(),
    )

    diagnostics = package.diagnostics
    assert package.decision.status == "success"
    assert diagnostics["blocked_reason"] is None
    assert len(diagnostics["task_queue"]) == 3
    assert [task["status"] for task in diagnostics["task_results"]] == ["completed", "completed", "completed"]
    assert set(package.changed_files) >= {"src/cli.py", "tests/test_cli.py", "README.md"}
    assert diagnostics["final_verification"]["passed"] is True
    assert diagnostics["final_review"]["approval"] is True
    assert package.review is not None
    assert package.review.approval is True
