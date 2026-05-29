import pytest

from my_coding_team.orchestration.task_runner import should_run_red
from my_coding_team.schemas.task import TaskContract
from my_coding_team.schemas.workflow import RepoContext, TeamState


def _contract(*, planning=None, files=None, commands=None):
    return TaskContract(
        task_id="T1",
        goal="edit",
        allowed_files=files or ["src/foo.py"],
        verification_commands=commands if commands is not None else ["python -m pytest"],
        test_first_requirement=planning,
    )


@pytest.mark.parametrize(
    ("planning", "files", "commands", "expected"),
    [
        ("required", ["src/foo.py"], ["python -m pytest"], True),
        ("not_applicable", ["src/foo.py"], ["python -m pytest"], True),
        ("required", ["README.md"], ["python -m pytest"], False),
        ("not_applicable", ["README.md"], ["python -m pytest"], False),
        (None, ["src/foo.py"], ["python -m pytest"], True),
        (None, ["docs/x.md"], ["python -m pytest"], False),
        ("optional", ["src/foo.py"], ["python -m pytest"], True),
        (None, ["src/foo.py"], [], False),
    ],
)
def test_should_run_red(planning, files, commands, expected):
    assert should_run_red(_contract(planning=planning, files=files, commands=commands)) is expected


def test_should_run_red_skips_without_test_entrypoints():
    contract = _contract(planning="required", files=["src/foo.py"], commands=["python -m pytest"])
    state = TeamState(request="add code", llm_calls_budget=12)

    assert should_run_red(contract, repo_context=RepoContext(test_entrypoints=[]), state=state) is False
    assert state.pm_overrides[0]["reason"] == "no test entrypoints in repo context"


def test_should_run_red_records_planning_pm_override_for_code_task():
    contract = _contract(planning="not_applicable", files=["src/foo.py"], commands=["python -m pytest"])
    state = TeamState(request="add code", llm_calls_budget=12)

    assert should_run_red(contract, repo_context=RepoContext(test_entrypoints=["pytest"]), state=state) is True
    assert state.pm_overrides[0]["planning_said"] == "not_applicable"
    assert state.pm_overrides[0]["pm_said"] is True


def test_should_run_red_records_planning_pm_override_for_docs_task():
    contract = _contract(planning="required", files=["README.md"], commands=["python -m pytest"])
    state = TeamState(request="update docs", llm_calls_budget=12)

    assert should_run_red(contract, repo_context=RepoContext(test_entrypoints=["pytest"]), state=state) is False
    assert state.pm_overrides[0]["final"] is False
    assert state.pm_overrides[0]["reason"] == "all allowed files are docs/config"
