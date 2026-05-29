import subprocess
from pathlib import Path

import pytest

from my_coding_team.agents import context_scout as _context_scout  # noqa: F401
from my_coding_team.core.registry import STEPS
from my_coding_team.core.step import StepContext
from my_coding_team.orchestration.workspace_manager import inspect_git_workspace, local_workspace
from my_coding_team.schemas.step_inputs import ContextScoutInput


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, check=True)


def test_workspace_manager_records_non_git_directory(tmp_path: Path):
    record = inspect_git_workspace(tmp_path)

    assert record.is_git is False
    assert record.dirty_files == []


def test_workspace_manager_records_dirty_git_directory(tmp_path: Path):
    _init_repo(tmp_path)
    (tmp_path / "README.md").write_text("dirty\n", encoding="utf-8")

    record = inspect_git_workspace(tmp_path)

    assert record.is_git is True
    assert "README.md" in record.status_short
    assert "README.md" in record.dirty_files


@pytest.mark.asyncio
async def test_context_scout_outputs_evidence(tmp_path: Path):
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    record = inspect_git_workspace(tmp_path)

    context = await STEPS["context_scout"].run(
        ContextScoutInput(request="inspect repo", workspace=record),
        StepContext(workspace_root=record.root),
    )

    assert "README.md" in context.relevant_files
    assert context.evidence


@pytest.mark.asyncio
async def test_local_workspace_lifecycle(tmp_path: Path):
    async with local_workspace(tmp_path) as workspace:
        assert workspace is not None
