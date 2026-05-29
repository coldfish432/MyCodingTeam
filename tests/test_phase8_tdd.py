from pathlib import Path
import asyncio

from my_coding_team.orchestration.task_runner import run_single_task, run_single_task_with_red
from my_coding_team.runtime.mock_model import DeterministicModel
from my_coding_team.schemas.common import Evidence
from my_coding_team.schemas.review import ReviewFinding, TaskReviewResult
from my_coding_team.schemas.task import TaskContract
from my_coding_team.schemas.workflow import RepoContext, TeamState


def _write_calc_repo(path: Path) -> None:
    utils = path / "utils"
    utils.mkdir()
    (utils / "__init__.py").write_text("from .calc import multiply\n", encoding="utf-8")
    (utils / "calc.py").write_text("def multiply(a, b):\n    return a * b\n", encoding="utf-8")
    tests = path / "tests"
    tests.mkdir()
    (tests / "test_calc.py").write_text(
        "from utils.calc import multiply\n\n"
        "def test_multiply():\n"
        "    assert multiply(2, 3) == 6\n",
        encoding="utf-8",
    )


def test_code_task_runs_red_then_green(tmp_path: Path):
    asyncio.run(_test_code_task_runs_red_then_green(tmp_path))


async def _test_code_task_runs_red_then_green(tmp_path: Path):
    _write_calc_repo(tmp_path)
    contract = TaskContract(
        task_id="T1",
        goal="add add function",
        allowed_files=["utils/calc.py", "tests/test_calc.py"],
        verification_commands=["python -m pytest"],
        test_first_requirement="required",
        red_allowed_files=["tests/test_calc.py"],
        red_verification_command="python -m pytest tests/test_calc.py",
        expected_failure_signature_hints=["ImportError"],
    )
    model = DeterministicModel(
        json_outputs=[
            {
                "summary": "add red test",
                "changes": [
                    {
                        "path": "tests/test_calc.py",
                        "content": (
                            "from utils.calc import multiply, add\n\n"
                            "def test_multiply():\n"
                            "    assert multiply(2, 3) == 6\n\n"
                            "def test_add():\n"
                            "    assert add(2, 3) == 5\n"
                        ),
                    }
                ],
                "expected_failure_signature": "ImportError cannot import name add",
                "failure_category": "import_error",
                "failure_excerpt": "ImportError: cannot import name add",
            },
            {
                "summary": "implement add",
                "changes": [
                    {
                        "path": "utils/calc.py",
                        "content": "def multiply(a, b):\n    return a * b\n\n\ndef add(a, b):\n    return a + b\n",
                    }
                ],
            },
        ]
    )

    result = await run_single_task_with_red(contract, tmp_path, implementation_model=model)

    assert result.blocked is False
    assert result.red is not None
    assert result.red.files_changed == ["tests/test_calc.py"]
    assert result.verification.passed is True


def test_red_mismatch_blocks_before_green(tmp_path: Path):
    asyncio.run(_test_red_mismatch_blocks_before_green(tmp_path))


async def _test_red_mismatch_blocks_before_green(tmp_path: Path):
    _write_calc_repo(tmp_path)
    contract = TaskContract(
        task_id="T1",
        goal="add add function",
        allowed_files=["utils/calc.py"],
        verification_commands=["python -m pytest"],
        test_first_requirement="required",
        red_allowed_files=["tests/test_calc.py"],
        red_verification_command="python -m pytest tests/test_calc.py",
    )
    model = DeterministicModel(
        json_outputs=[
            {
                "summary": "bad red signature",
                "changes": [
                    {
                        "path": "tests/test_calc.py",
                        "content": (
                            "from utils.calc import add\n\n"
                            "def test_add():\n"
                            "    assert add(2, 3) == 5\n"
                        ),
                    }
                ],
                "expected_failure_signature": "AssertionError wrong value",
                "failure_category": "assertion",
                "failure_excerpt": "ImportError: cannot import name add",
            },
            {
                "summary": "should not be used",
                "changes": [{"path": "utils/calc.py", "content": "bad\n"}],
            },
        ]
    )

    result = await run_single_task_with_red(contract, tmp_path, implementation_model=model)

    assert result.blocked is True
    assert result.blocked_reason == "blocked_by_red_mismatch"
    assert (tmp_path / "utils" / "calc.py").read_text(encoding="utf-8") == "def multiply(a, b):\n    return a * b\n"


def test_docs_task_skips_red(tmp_path: Path):
    asyncio.run(_test_docs_task_skips_red(tmp_path))


async def _test_docs_task_skips_red(tmp_path: Path):
    (tmp_path / "README.md").write_text("old\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    contract = TaskContract(
        task_id="T1",
        goal="update docs",
        allowed_files=["README.md"],
        verification_commands=["python -m pytest"],
        test_first_requirement="not_applicable",
    )
    model = DeterministicModel(
        json_outputs=[
            {
                "summary": "update docs",
                "changes": [{"path": "README.md", "content": "new\n"}],
            }
        ]
    )

    result = await run_single_task_with_red(contract, tmp_path, implementation_model=model)

    assert result.blocked is False
    assert result.red is None
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "new\n"


def test_config_task_skips_red(tmp_path: Path):
    asyncio.run(_test_config_task_skips_red(tmp_path))


async def _test_config_task_skips_red(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = \"demo\"\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    contract = TaskContract(
        task_id="T1",
        goal="update config",
        allowed_files=["pyproject.toml"],
        verification_commands=["python -m pytest"],
        test_first_requirement="required",
    )
    state = TeamState(request="update config", llm_calls_budget=12)
    model = DeterministicModel(
        json_outputs=[
            {
                "summary": "update config",
                "changes": [{"path": "pyproject.toml", "content": "[project]\nname = \"demo\"\nversion = \"0.1.0\"\n"}],
            }
        ]
    )

    result = await run_single_task_with_red(
        contract,
        tmp_path,
        state=state,
        implementation_model=model,
        repo_context=RepoContext(test_entrypoints=["pytest"]),
    )

    assert result.blocked is False
    assert result.red is None
    assert state.pm_overrides[0]["reason"] == "all allowed files are docs/config"


def test_no_test_framework_skips_red_and_records_override(tmp_path: Path):
    _write_calc_repo(tmp_path)
    contract = TaskContract(
        task_id="T1",
        goal="add code",
        allowed_files=["utils/calc.py"],
        verification_commands=["python -m pytest"],
        test_first_requirement="required",
    )
    state = TeamState(request="add code", llm_calls_budget=12)

    result = asyncio.run(
        run_single_task_with_red(
            contract,
            tmp_path,
            state=state,
            implementation_model=DeterministicModel(
                json_outputs=[
                    {
                        "summary": "noop",
                        "changes": [{"path": "utils/calc.py", "content": "def multiply(a, b):\n    return a * b\n"}],
                    }
                ]
            ),
            repo_context=RepoContext(test_entrypoints=[]),
        )
    )

    assert result.red is None
    assert state.pm_overrides[0]["reason"] == "no test entrypoints in repo context"


def test_bad_red_category_blocks_before_green(tmp_path: Path):
    asyncio.run(_test_bad_red_category_blocks_before_green(tmp_path))


async def _test_bad_red_category_blocks_before_green(tmp_path: Path):
    _write_calc_repo(tmp_path)
    contract = TaskContract(
        task_id="T1",
        goal="add add function",
        allowed_files=["utils/calc.py"],
        verification_commands=["python -m pytest"],
        test_first_requirement="required",
        red_allowed_files=["tests/test_calc.py"],
        red_verification_command="python -m pytest tests/test_calc.py",
    )
    model = DeterministicModel(
        json_outputs=[
            {
                "summary": "bad syntax red",
                "changes": [{"path": "tests/test_calc.py", "content": "def test_bad(:\n    pass\n"}],
                "expected_failure_signature": "SyntaxError",
                "failure_category": "syntax_error",
                "failure_excerpt": "SyntaxError: invalid syntax",
            },
            {"summary": "should not run", "changes": [{"path": "utils/calc.py", "content": "bad\n"}]},
        ]
    )

    result = await run_single_task_with_red(contract, tmp_path, implementation_model=model)

    assert result.blocked is True
    assert result.blocked_reason == "blocked_by_red_mismatch"
    assert result.red.failure_category == "syntax_error"


def test_repair_expands_allowed_files_only_for_test_quality_review(tmp_path: Path, monkeypatch):
    asyncio.run(_test_repair_expands_allowed_files_only_for_test_quality_review(tmp_path, monkeypatch))


async def _test_repair_expands_allowed_files_only_for_test_quality_review(tmp_path: Path, monkeypatch):
    _write_calc_repo(tmp_path)
    contract = TaskContract(
        task_id="T1",
        goal="repair test",
        allowed_files=["utils/calc.py"],
        verification_commands=["python -m pytest"],
        test_first_requirement="not_applicable",
        red_allowed_files=["tests/test_calc.py"],
    )
    seen_allowed_files = []

    reviews = [
        TaskReviewResult(
            task_id="T1",
            approval=False,
            summary="bad test",
            findings=[
                ReviewFinding(
                    finding_id="red_test_quality",
                    title="RED test failed for an unacceptable reason",
                    severity="high",
                    approval=False,
                    must_fix=["Fix RED test quality before delivery."],
                    evidence=[Evidence(path="tests/test_calc.py", note="bad red")],
                )
            ],
        ),
        TaskReviewResult(task_id="T1", approval=True, summary="approved"),
    ]

    class FakeImplementationRoom:
        async def execute(self, input, context):
            from my_coding_team.schemas.task import ImplementationResult, TaskContract, TaskRepairContract

            current_contract = (
                TaskRepairContract.model_validate(input.contract)
                if "original_task_id" in input.contract
                else TaskContract.model_validate(input.contract)
            )
            seen_allowed_files.append(list(current_contract.allowed_files))
            return ImplementationResult(task_id="T1", success=True, changed_files=[])

    class FakeQAStep:
        async def run(self, input, context):
            from my_coding_team.schemas.task import VerificationResult

            return VerificationResult(task_id="T1", passed=True, commands=["python -m pytest"])

    class FakeReviewRoom:
        async def execute(self, input, context):
            return reviews.pop(0)

    from my_coding_team.orchestration import task_runner

    monkeypatch.setitem(task_runner.ROOMS, "implementation_room", FakeImplementationRoom())
    monkeypatch.setitem(task_runner.STEPS, "qa_verification", FakeQAStep())
    monkeypatch.setitem(task_runner.ROOMS, "review_room", FakeReviewRoom())

    result = await run_single_task(contract, tmp_path, implementation_model=object(), max_repairs=1)

    assert result.blocked is False
    assert seen_allowed_files[0] == ["utils/calc.py"]
    assert seen_allowed_files[1] == ["utils/calc.py", "tests/test_calc.py"]
