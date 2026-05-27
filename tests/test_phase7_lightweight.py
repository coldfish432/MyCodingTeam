import subprocess
from pathlib import Path

import pytest

from my_coding_team.agents.planning import call_planning_for_single_contract
from my_coding_team.agents.qa_verification import call_qa_verification
from my_coding_team.agents.review_room import call_review_room
from my_coding_team.agents.task_implementation import call_task_implementation
from my_coding_team.orchestration.pm_orchestrator import run_request
from my_coding_team.orchestration.task_runner import run_single_task
from my_coding_team.runtime.mock_model import DeterministicModel
from my_coding_team.schemas.task import ImplementationResult, TaskContract, VerificationResult
from my_coding_team.schemas.workflow import RepoContext, WorkspaceRecord


def _repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, check=True)


def _pytest_file(path: Path, filename: str) -> None:
    tests = path / "tests"
    tests.mkdir()
    (tests / filename).write_text("def test_ok():\n    assert True\n", encoding="utf-8")


@pytest.mark.asyncio
async def test_planning_generates_single_task_contract():
    model = DeterministicModel(
        json_outputs=[
            {
                "task_id": "T1",
                "objective": "update README",
                "allowed_files": ["README.md"],
                "verification_commands": ["python -m pytest"],
            }
        ]
    )

    contract = await call_planning_for_single_contract(
        "update README",
        RepoContext(relevant_files=["README.md"], test_entrypoints=["tests/test_ok.py"]),
        WorkspaceRecord(root=".", is_git=False),
        model=model,
    )

    assert contract.allowed_files == ["README.md"]
    assert contract.verification_commands == ["python -m pytest"]


@pytest.mark.asyncio
async def test_planning_replaces_unsafe_verification_command():
    model = DeterministicModel(
        json_outputs=[
            {
                "task_id": "T1",
                "objective": "update README",
                "allowed_files": ["README.md"],
                "verification_commands": ["python -c \"print('unsafe')\""],
            }
        ]
    )

    contract = await call_planning_for_single_contract(
        "update README",
        RepoContext(relevant_files=["README.md"], test_entrypoints=["tests/test_ok.py"]),
        WorkspaceRecord(root=".", is_git=False),
        model=model,
    )

    assert contract.verification_commands == ["python -m pytest"]


@pytest.mark.asyncio
async def test_task_implementation_rejects_unauthorized_file(tmp_path: Path):
    contract = TaskContract(
        task_id="T1",
        objective="edit",
        allowed_files=["README.md"],
        verification_commands=["python -m pytest"],
    )
    model = DeterministicModel(
        json_outputs=[{"changes": [{"path": "outside.txt", "content": "bad"}]}]
    )

    with pytest.raises(PermissionError):
        await call_task_implementation(contract, tmp_path, model=model)


@pytest.mark.asyncio
async def test_task_runner_converts_permission_error_to_blocked(tmp_path: Path):
    contract = TaskContract(
        task_id="T1",
        objective="edit",
        allowed_files=["README.md"],
        verification_commands=["python -m pytest"],
    )
    model = DeterministicModel(
        json_outputs=[{"changes": [{"path": "outside.txt", "content": "bad"}]}]
    )

    result = await run_single_task(contract, tmp_path, implementation_model=model)

    assert result.blocked is True
    assert result.blocked_reason == "blocked_by_permission_denied"
    assert not (tmp_path / "outside.txt").exists()


@pytest.mark.asyncio
async def test_qa_runs_only_contract_commands(tmp_path: Path):
    _pytest_file(tmp_path, "test_ok.py")
    contract = TaskContract(
        task_id="T1",
        objective="verify",
        allowed_files=["README.md"],
        verification_commands=["python -m pytest"],
    )

    result = await call_qa_verification(contract, tmp_path)

    assert result.passed is True
    assert result.commands == ["python -m pytest"]


@pytest.mark.asyncio
async def test_review_blocks_failed_verification():
    contract = TaskContract(
        task_id="T1",
        objective="verify",
        allowed_files=["README.md"],
        verification_commands=["python -m pytest"],
    )
    review = await call_review_room(
        contract,
        ImplementationResult(task_id="T1", success=True),
        VerificationResult(task_id="T1", passed=False, failed_commands=["python -m pytest"]),
    )

    assert review.approval is False
    assert review.findings[0].must_fix


@pytest.mark.asyncio
async def test_lightweight_flow_completes_doc_task(tmp_path: Path):
    _repo(tmp_path)
    (tmp_path / "README.md").write_text("old\n", encoding="utf-8")
    _pytest_file(tmp_path, "test_ok.py")
    model = DeterministicModel(
        json_outputs=[
            {
                "task_id": "T1",
                "objective": "update README",
                "allowed_files": ["README.md"],
                "verification_commands": ["python -m pytest"],
            },
            {
                "summary": "updated README",
                "changes": [{"path": "README.md", "content": "new\n"}],
            },
        ]
    )

    package = await run_request(
        "新增 README 内容",
        mode="lightweight",
        workspace=tmp_path,
        model=model,
    )

    assert package.decision.status == "success"
    assert package.changed_files == ["README.md"]
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "new\n"


@pytest.mark.asyncio
async def test_repair_loop_blocks_after_two_attempts(tmp_path: Path):
    contract = TaskContract(
        task_id="T1",
        objective="edit",
        allowed_files=["README.md"],
        verification_commands=["python -m pytest"],
    )
    model = DeterministicModel(
        json_outputs=[
            {"changes": [{"path": "README.md", "content": "try1\n"}]},
            {"changes": [{"path": "README.md", "content": "try2\n"}]},
            {"changes": [{"path": "README.md", "content": "try3\n"}]},
        ]
    )

    result = await run_single_task(contract, tmp_path, implementation_model=model, max_repairs=2)

    assert result.blocked is True
    assert result.blocked_reason == "blocked_by_repair_limit"
