r"""Phase 9 Full Product Flow real-LLM smoke runner.

Usage:
    .venv\Scripts\python.exe tests\smoke\full_product_smoke_runner.py
    .venv\Scripts\python.exe tests\smoke\full_product_smoke_runner.py --case FF-C

FF-A and FF-B simulate Y at the design signoff gate. FF-C simulates N so the
gate can be tested in non-interactive smoke runs.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from my_coding_team.orchestration.pm_orchestrator import run_request
from my_coding_team.config import load_config
from my_coding_team.runtime.llm_client import OpenAICompatibleModel
from my_coding_team.schemas.delivery import DeliveryPackage

SMOKE_ROOT = ROOT / ".my_coding_team" / "smoke_runs" / "phase9"
REPORT_PATH = ROOT / "tests" / "smoke" / "PHASE9_SMOKE_RESULTS.md"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


@dataclass
class CaseResult:
    case: str
    request: str
    expected: str
    workspace: str
    verdict: str
    status: str
    llm_calls: int
    budget: int
    changed_files: list[str] = field(default_factory=list)
    blocked_reason: str = ""
    task_count: int = 0
    task_statuses: list[str] = field(default_factory=list)
    final_verification: str = "not_run"
    final_review: str = "not_run"
    notes: str = ""
    error: str = ""


def _prepare_calc_workspace(suffix: str = "") -> Path:
    import uuid

    tag = suffix or uuid.uuid4().hex[:8]
    ws = SMOKE_ROOT / f"calc_project_{tag}"
    if ws.exists():
        raise RuntimeError(f"smoke workspace already exists: {ws}")
    ws.mkdir(parents=True, exist_ok=True)

    (ws / "src").mkdir(exist_ok=True)
    (ws / "tests").mkdir(exist_ok=True)
    (ws / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "calc"
version = "0.1.0"
""",
        encoding="utf-8",
    )
    (ws / "src" / "__init__.py").write_text("", encoding="utf-8")
    (ws / "src" / "calc.py").write_text(
        '''"""Simple calculator module."""

def multiply(a, b):
    """Multiply two numbers."""
    return a * b
''',
        encoding="utf-8",
    )
    (ws / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (ws / "tests" / "test_calc.py").write_text(
        """from src.calc import multiply

def test_multiply():
    assert multiply(2, 3) == 6
    assert multiply(0, 5) == 0
""",
        encoding="utf-8",
    )

    subprocess.run(["git", "init"], cwd=ws, capture_output=True, check=False)
    subprocess.run(["git", "config", "user.email", "smoke@test.local"], cwd=ws, capture_output=True, check=False)
    subprocess.run(["git", "config", "user.name", "Smoke Test"], cwd=ws, capture_output=True, check=False)
    subprocess.run(["git", "add", "-A"], cwd=ws, capture_output=True, check=False)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=ws, capture_output=True, check=False)
    return ws


def _git_changed_files(workspace: Path) -> list[str]:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    files: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        normalized = path.replace("\\", "/")
        if "__pycache__/" in normalized or normalized.endswith(".pyc"):
            continue
        files.append(normalized)
    return files


def _diagnostics(pkg: DeliveryPackage | None, workspace: Path) -> dict:
    if pkg is None:
        return {
            "status": "none",
            "blocked_reason": "",
            "changed_files": _git_changed_files(workspace),
            "task_results": [],
            "final_verification": None,
            "final_review": None,
        }

    diagnostics = pkg.diagnostics or {}
    changed_files = list(pkg.changed_files or [])
    for path in _git_changed_files(workspace):
        if path not in changed_files:
            changed_files.append(path)
    return {
        "status": pkg.decision.status,
        "blocked_reason": diagnostics.get("blocked_reason") or pkg.decision.reason,
        "changed_files": changed_files,
        "task_results": diagnostics.get("task_results") or [],
        "final_verification": diagnostics.get("final_verification"),
        "final_review": diagnostics.get("final_review"),
    }


def _final_verification_summary(value) -> str:
    if not value:
        return "not_run"
    status = "passed" if value.get("passed") else "failed"
    failed = value.get("failed_commands") or []
    if failed:
        return f"{status}; failed={', '.join(failed)}"
    return status


def _final_review_summary(value) -> str:
    if not value:
        return "not_run"
    approval = value.get("approval")
    findings = value.get("findings") or []
    titles = [f.get("title", "") for f in findings[:3] if isinstance(f, dict)]
    suffix = f"; findings={len(findings)}"
    if titles:
        suffix += f"; titles={'; '.join(titles)}"
    return f"approval={approval}{suffix}"


@contextmanager
def _simulated_signoff(choice: str, reason: str | None = None):
    old_choice = os.environ.get("MY_CODING_TEAM_SIGNOFF_CHOICE")
    old_reason = os.environ.get("MY_CODING_TEAM_SIGNOFF_REASON")
    os.environ["MY_CODING_TEAM_SIGNOFF_CHOICE"] = choice
    if reason is not None:
        os.environ["MY_CODING_TEAM_SIGNOFF_REASON"] = reason
    else:
        os.environ.pop("MY_CODING_TEAM_SIGNOFF_REASON", None)
    try:
        yield
    finally:
        if old_choice is None:
            os.environ.pop("MY_CODING_TEAM_SIGNOFF_CHOICE", None)
        else:
            os.environ["MY_CODING_TEAM_SIGNOFF_CHOICE"] = old_choice
        if old_reason is None:
            os.environ.pop("MY_CODING_TEAM_SIGNOFF_REASON", None)
        else:
            os.environ["MY_CODING_TEAM_SIGNOFF_REASON"] = old_reason


async def _run_case(
    request: str,
    workspace: Path,
    budget: int,
    *,
    signoff_choice: str,
    signoff_reason: str | None = None,
) -> tuple[DeliveryPackage | None, str]:
    try:
        model = OpenAICompatibleModel(config=load_config(cwd=ROOT), timeout_seconds=180)
        with _simulated_signoff(signoff_choice, signoff_reason):
            pkg = await run_request(
                request,
                budget=budget,
                workspace=str(workspace),
                mode="full",
                model=model,
            )
        return pkg, ""
    except Exception as exc:
        return None, str(exc)


def _result_from_pkg(
    *,
    case: str,
    request: str,
    expected: str,
    workspace: Path,
    budget: int,
    pkg: DeliveryPackage | None,
    error: str,
    expected_files: set[str],
    require_final_review: bool,
    require_success: bool = True,
) -> CaseResult:
    diag = _diagnostics(pkg, workspace)
    task_results = diag["task_results"]
    task_statuses = [str(item.get("status", "unknown")) for item in task_results if isinstance(item, dict)]
    changed_files = diag["changed_files"]
    missing_files = sorted(expected_files.difference(changed_files))
    final_review = diag["final_review"]

    pass_conditions = [
        not error,
        diag["status"] == "success" if require_success else diag["status"] == "blocked",
        bool(changed_files),
        not missing_files,
        bool(task_results),
        all(status == "completed" for status in task_statuses),
    ]
    if require_final_review:
        pass_conditions.append(bool(final_review))

    verdict = "pass" if all(pass_conditions) else "fail"
    notes = []
    if missing_files:
        notes.append(f"missing_expected_files={','.join(missing_files)}")
    if error:
        notes.append(f"error={error}")
    if diag["blocked_reason"]:
        notes.append(f"blocked_reason={diag['blocked_reason']}")

    return CaseResult(
        case=case,
        request=request,
        expected=expected,
        workspace=str(workspace),
        verdict=verdict,
        status=diag["status"],
        llm_calls=pkg.llm_calls_used if pkg else 0,
        budget=budget,
        changed_files=changed_files,
        blocked_reason=diag["blocked_reason"],
        task_count=len(task_results),
        task_statuses=task_statuses,
        final_verification=_final_verification_summary(diag["final_verification"]),
        final_review=_final_review_summary(final_review),
        notes="; ".join(notes) if notes else "ok",
        error=error,
    )


async def run_ff_a(workspace: Path) -> CaseResult:
    request = (
        "Add a CLI command to the existing calc library. Create src/cli.py so "
        "`calc-cli add 3 5` prints 8. Include the CLI module, unit tests, and "
        "a README usage update."
    )
    pkg, error = await _run_case(request, workspace, budget=50, signoff_choice="y")
    return _result_from_pkg(
        case="FF-A",
        request=request,
        expected="3-task happy path reaches success with CLI, tests, README changes",
        workspace=workspace,
        budget=50,
        pkg=pkg,
        error=error,
        expected_files={"src/cli.py", "README.md"},
        require_final_review=True,
    )


async def run_ff_b(workspace: Path) -> CaseResult:
    request = (
        "Add a simple event logging system. Create src/logger.py with a log "
        "function, call it from src/calc.py multiply, and write tests covering it."
    )
    pkg, error = await _run_case(request, workspace, budget=70, signoff_choice="y")
    return _result_from_pkg(
        case="FF-B",
        request=request,
        expected="cross-task work reaches Final Review with concrete final findings",
        workspace=workspace,
        budget=70,
        pkg=pkg,
        error=error,
        expected_files={"src/logger.py", "src/calc.py"},
        require_final_review=True,
    )


async def run_ff_c(workspace: Path) -> CaseResult:
    request = "Completely rewrite the project architecture from monolith to microservices."
    pkg, error = await _run_case(
        request,
        workspace,
        budget=10,
        signoff_choice="n",
        signoff_reason="smoke_rejected_signoff",
    )
    diag = _diagnostics(pkg, workspace)
    task_results = diag["task_results"]
    verdict = "pass" if (
        not error
        and diag["status"] == "blocked"
        and diag["blocked_reason"] == "smoke_rejected_signoff"
        and not task_results
        and 2 <= (pkg.llm_calls_used if pkg else 0) <= 8
    ) else "fail"
    return CaseResult(
        case="FF-C",
        request=request,
        expected="simulated N rejects signoff before Planning Queue",
        workspace=str(workspace),
        verdict=verdict,
        status=diag["status"],
        llm_calls=pkg.llm_calls_used if pkg else 0,
        budget=10,
        changed_files=diag["changed_files"],
        blocked_reason=diag["blocked_reason"],
        task_count=len(task_results),
        task_statuses=[str(item.get("status", "unknown")) for item in task_results if isinstance(item, dict)],
        final_verification=_final_verification_summary(diag["final_verification"]),
        final_review=_final_review_summary(diag["final_review"]),
        notes="simulated N signoff rejection path checked",
        error=error,
    )


def write_report(results: list[CaseResult], model_name: str) -> None:
    lines = [
        "# Phase 9 Full Product Flow Smoke Results",
        "",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Model: {model_name}",
        "",
        "| Case | Result | Status | LLM calls | Budget | Changed files | Tasks | Final verification | Final review | Notes |",
        "| --- | --- | --- | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        files = ", ".join(r.changed_files[:8])
        if len(r.changed_files) > 8:
            files += f" ... (+{len(r.changed_files) - 8})"
        task_statuses = ",".join(r.task_statuses) if r.task_statuses else "none"
        tasks = f"{r.task_count} [{task_statuses}]"
        lines.append(
            f"| {r.case} | {r.verdict} | {r.status} | {r.llm_calls} | {r.budget} | "
            f"{files} | {tasks} | {r.final_verification} | {r.final_review} | {r.notes} |"
        )

    lines.extend(["", "## Blocking / Inconclusive Items", ""])
    failed = [r for r in results if r.verdict != "pass"]
    if failed:
        for r in failed:
            reason = r.error or r.blocked_reason or r.notes
            lines.append(f"- **{r.case}**: {reason}")
    else:
        lines.append("- No blocking issues found.")

    lines.extend(
        [
            "",
            "## Acceptance Rules",
            "",
            "- FF-A only passes with simulated `Y`, `status=success`, non-empty changed files, expected files, completed task results, final verification, and final review.",
            "- FF-B only passes with simulated `Y`, `status=success`, expected cross-task files, completed task results, and concrete final review output.",
            "- FF-C only passes with simulated `N`, `status=blocked`, `blocked_reason=smoke_rejected_signoff`, no task results, and no Planning Queue execution.",
        ]
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written: {REPORT_PATH}")


def _model_name() -> str:
    return load_config(cwd=ROOT).model_name or "unknown"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=["FF-A", "FF-B", "FF-C", "all"], default="all")
    args = parser.parse_args()

    print(f"Phase 9 Full Flow Smoke - model: {_model_name()}")
    print()

    selected = ["FF-A", "FF-B", "FF-C"] if args.case == "all" else [args.case]
    results: list[CaseResult] = []

    for case in selected:
        print(f"=== {case} ===")
        ws = _prepare_calc_workspace()
        if case == "FF-A":
            result = await run_ff_a(ws)
        elif case == "FF-B":
            result = await run_ff_b(ws)
        else:
            result = await run_ff_c(ws)
        results.append(result)
        print(f"  {result.verdict}: status={result.status}; tasks={result.task_count}; notes={result.notes}")

    write_report(results, _model_name())
    passed = sum(1 for r in results if r.verdict == "pass")
    print(f"\nSummary: {passed}/{len(results)} passed")


if __name__ == "__main__":
    asyncio.run(main())
