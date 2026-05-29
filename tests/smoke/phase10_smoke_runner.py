"""Real LLM smoke runner for Phase 10 Review-Only Flow."""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from my_coding_team.orchestration.pm_orchestrator import run_request
from my_coding_team.runtime.llm_client import OpenAICompatibleModel


ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "PHASE10_SMOKE_RESULTS.md"


@dataclass
class SmokeCase:
    case_id: str
    description: str
    request: str
    mode: str
    files: dict[str, str]
    dirty_updates: dict[str, str] | None = None
    pasted_content: str | None = None
    expect_must_fix: bool = False
    expect_clean: bool = False
    expect_hint: bool = False
    expect_line_evidence: bool = False


def _repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, check=True)


def _write_files(root: Path, files: dict[str, str]) -> None:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _must_fix_count(package) -> int:
    if package.review is None or not package.review.findings:
        return 0
    return len(package.review.findings[0].must_fix)


def _evidence_paths(package) -> list[str]:
    if package.review is None or not package.review.findings:
        return []
    return [e.path for e in package.review.findings[0].evidence]


async def _run_case(case: SmokeCase, model) -> dict:
    with TemporaryDirectory(prefix=f"phase10_{case.case_id}_") as tmp:
        workspace = Path(tmp)
        _repo(workspace)
        _write_files(workspace, case.files)
        subprocess.run(["git", "add", "."], cwd=workspace, check=True)
        subprocess.run(["git", "commit", "-m", "init", "-q"], cwd=workspace, check=True)
        if case.dirty_updates:
            _write_files(workspace, case.dirty_updates)

        package = await run_request(
            case.request,
            mode=case.mode,
            workspace=workspace,
            budget=8,
            model=model,
            pasted_content=case.pasted_content,
        )

        must_fix = _must_fix_count(package)
        hint = package.diagnostics.get("next_step_hint")
        evidence_paths = _evidence_paths(package)
        checks = [
            package.decision.status == "success",
            package.workflow_kind == "review_only",
            package.changed_files == [],
        ]
        if case.expect_must_fix:
            checks.append(must_fix > 0)
        if case.expect_clean:
            checks.append(must_fix == 0)
        if case.expect_hint:
            checks.append(bool(hint))
        if case.expect_line_evidence:
            checks.append(any(path.startswith("L") for path in evidence_paths))

        return {
            "case_id": case.case_id,
            "description": case.description,
            "verdict": "pass" if all(checks) else "fail",
            "status": package.decision.status,
            "must_fix_count": must_fix,
            "changed_files": package.changed_files,
            "next_step_hint": hint,
            "evidence": evidence_paths,
            "summary": package.summary,
        }


async def main() -> int:
    model = OpenAICompatibleModel.from_env()
    cases = [
        SmokeCase(
            case_id="RO-A",
            description="file_list bug review",
            request="review src/calc.py",
            mode="review-only",
            files={"src/calc.py": "def last_item(items):\n    return items[len(items)]\n"},
            expect_must_fix=True,
            expect_hint=True,
        ),
        SmokeCase(
            case_id="RO-B",
            description="workspace_diff dirty repo review",
            request="look at my changes",
            mode="review-only",
            files={"src/app.py": "def total(items):\n    return sum(items)\n"},
            dirty_updates={"src/app.py": "def total(items):\n    return sum(items) / len(items)\n"},
        ),
        SmokeCase(
            case_id="RO-C",
            description="clean code should not fabricate must_fix",
            request="review src/calc.py",
            mode="review-only",
            files={"src/calc.py": "def add(a, b):\n    return a + b\n"},
            expect_clean=True,
        ),
        SmokeCase(
            case_id="RO-D",
            description="security issue review",
            request="review src/db.py",
            mode="review-only",
            files={"src/db.py": "def find_user(conn, name):\n    return conn.execute(\"select * from users where name = '\" + name + \"'\")\n"},
            expect_must_fix=True,
            expect_hint=True,
        ),
        SmokeCase(
            case_id="RO-E",
            description="pasted snippet line evidence",
            request="review the pasted python",
            mode="review-only",
            files={"README.md": "placeholder\n"},
            pasted_content="def item_at(items, index):\n    if index > len(items):\n        return None\n    return items[index]\n",
            expect_must_fix=True,
            expect_hint=True,
            expect_line_evidence=True,
        ),
        SmokeCase(
            case_id="RO-F",
            description="workspace_diff next_step_hint",
            request="look at my changes",
            mode="review-only",
            files={"src/db.py": "def query(conn, value):\n    return conn.execute('select 1')\n"},
            dirty_updates={"src/db.py": "def query(conn, value):\n    return conn.execute('select * from t where v=' + value)\n"},
            expect_must_fix=True,
            expect_hint=True,
        ),
    ]
    results = []
    for case in cases:
        results.append(await _run_case(case, model))

    passed = sum(1 for result in results if result["verdict"] == "pass")
    lines = [
        "# Phase 10 Review-Only Smoke Results",
        "",
        "Date: 2026-05-28",
        "Model: deepseek-v4-flash",
        "",
        f"Summary: {passed}/{len(results)} passed",
        "",
        "| Case | Verdict | Status | must_fix | changed_files | Evidence | next_step_hint |",
        "|---|---|---|---:|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| {case_id} | {verdict} | {status} | {must_fix_count} | {changed_files} | {evidence} | {hint} |".format(
                case_id=result["case_id"],
                verdict=result["verdict"],
                status=result["status"],
                must_fix_count=result["must_fix_count"],
                changed_files=", ".join(result["changed_files"]) or "[]",
                evidence=", ".join(result["evidence"]) or "[]",
                hint="yes" if result["next_step_hint"] else "no",
            )
        )
    lines.extend(["", "## Notes", "", "Review-only must keep `changed_files=[]` for every case."])
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT_PATH)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
