import subprocess
from pathlib import Path

import pytest

from my_coding_team.orchestration.review_input_materializer import (
    materialize_review_input,
    summarize_review_input,
)
from my_coding_team.schemas.workflow import ReviewOnlyInput, WorkspaceRecord


def _repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, check=True)


@pytest.mark.asyncio
async def test_file_list_materializes_file_contents(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    blob = await materialize_review_input(
        ReviewOnlyInput(input_kind="file_list", files_to_review=["src/app.py"]),
        WorkspaceRecord(root=str(tmp_path), is_git=False),
    )

    assert "=== FILE: src/app.py ===" in blob
    assert "return a + b" in blob


@pytest.mark.asyncio
async def test_file_list_rejects_outside_workspace(tmp_path: Path):
    with pytest.raises(PermissionError):
        await materialize_review_input(
            ReviewOnlyInput(input_kind="file_list", files_to_review=["../outside.py"]),
            tmp_path,
        )


@pytest.mark.asyncio
async def test_workspace_diff_materializes_git_diff(tmp_path: Path):
    _repo(tmp_path)
    (tmp_path / "app.py").write_text("old = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "app.py").write_text("new = 2\n", encoding="utf-8")

    blob = await materialize_review_input(ReviewOnlyInput(input_kind="workspace_diff"), tmp_path)

    assert "diff --git" in blob
    assert "+new = 2" in blob


@pytest.mark.asyncio
async def test_pasted_text_materializes_without_workspace(tmp_path: Path):
    blob = await materialize_review_input(
        ReviewOnlyInput(input_kind="pasted_text", pasted_content="def f():\n    return 1\n"),
        tmp_path,
    )

    assert blob.startswith("def f")
    assert "pasted python" in summarize_review_input(
        ReviewOnlyInput(input_kind="pasted_text", pasted_content=blob, pasted_language_hint="python"),
        blob,
    )
