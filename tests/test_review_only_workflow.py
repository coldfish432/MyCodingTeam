import subprocess
from pathlib import Path

import pytest

from my_coding_team.agents.review_room import build_next_step_hint
from my_coding_team.orchestration.pm_orchestrator import run_request
from my_coding_team.runtime.mock_model import DeterministicModel
from my_coding_team.schemas.common import Evidence
from my_coding_team.schemas.review import ReviewFinding
from my_coding_team.schemas.workflow import ReviewOnlyInput


def _repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, check=True)


@pytest.mark.asyncio
async def test_review_only_file_list_produces_report_without_writes(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def div(a, b):\n    return a / b\n", encoding="utf-8")
    model = DeterministicModel(
        json_outputs=[
            {
                "finding_id": "zero_division",
                "title": "Missing zero division guard",
                "severity": "medium",
                "approval": False,
                "must_fix": ["Handle b == 0 before division."],
                "evidence": [{"path": "src/app.py", "line": 2, "note": "division by b"}],
                "file_path": "src/app.py",
                "line": 2,
            }
        ]
    )

    package = await run_request(
        "review src/app.py",
        mode="review-only",
        workspace=tmp_path,
        model=model,
    )

    assert package.decision.status == "success"
    assert package.workflow_kind == "review_only"
    assert package.changed_files == []
    assert package.review.findings[0].must_fix
    assert "my-coding-team run" in package.diagnostics["next_step_hint"]


@pytest.mark.asyncio
async def test_review_only_workspace_diff_allows_dirty_workspace(tmp_path: Path):
    _repo(tmp_path)
    (tmp_path / "app.py").write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "app.py").write_text("value = 2\n", encoding="utf-8")
    model = DeterministicModel(
        json_outputs=[
            {
                "finding_id": "clean",
                "title": "No blocking concerns",
                "severity": "low",
                "approval": True,
                "must_fix": [],
                "evidence": [],
            }
        ]
    )

    package = await run_request(
        "look at my changes",
        mode="review-only",
        workspace=tmp_path,
        model=model,
    )

    assert package.decision.status == "success"
    assert package.changed_files == []
    assert package.diagnostics["review_only_input"]["input_kind"] == "workspace_diff"
    assert package.diagnostics["next_step_hint"] is None


@pytest.mark.asyncio
async def test_review_only_pasted_text_skips_workspace_context(tmp_path: Path):
    model = DeterministicModel(
        json_outputs=[
            {
                "finding_id": "off_by_one",
                "title": "Loop misses the final item",
                "severity": "medium",
                "approval": False,
                "must_fix": ["Loop range excludes the last item."],
                "evidence": [{"path": "L2", "note": "range end"}],
            }
        ]
    )

    package = await run_request(
        "review the code",
        mode="review-only",
        workspace=tmp_path,
        model=model,
        pasted_content="for i in range(len(items) - 1):\n    use(items[i])\n",
    )

    assert package.decision.status == "success"
    assert package.diagnostics["review_only_input"]["input_kind"] == "pasted_text"
    assert package.diagnostics["artifacts"] == {}
    assert "paste the content into a file" in package.diagnostics["next_step_hint"]


def test_next_step_hint_variants():
    clean = ReviewFinding(finding_id="clean", title="Clean")
    assert build_next_step_hint(ReviewOnlyInput(input_kind="file_list", files_to_review=["a.py"]), clean) is None

    finding = ReviewFinding(
        finding_id="bug",
        title="Bug",
        approval=False,
        must_fix=["Fix it"],
        evidence=[Evidence(path="a.py", note="bug")],
    )
    assert "a.py" in build_next_step_hint(
        ReviewOnlyInput(input_kind="file_list", files_to_review=["a.py"]),
        finding,
    )
    assert "the changed files" in build_next_step_hint(ReviewOnlyInput(input_kind="workspace_diff"), finding)
    assert "paste the content into a file" in build_next_step_hint(
        ReviewOnlyInput(input_kind="pasted_text", pasted_content="x"),
        finding,
    )
