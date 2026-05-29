"""Run real-LLM smoke cases and write REAL_SMOKE_RESULTS.md."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from my_coding_team.orchestration.pm_orchestrator import run_request
from my_coding_team.orchestration.task_runner import run_single_task, run_single_task_with_red
from my_coding_team.runtime.llm_client import OpenAICompatibleModel
from my_coding_team.schemas.task import TaskContract
from my_coding_team.schemas.workflow import RepoContext, TeamState


SMOKE_ROOT = ROOT / ".my_coding_team" / "smoke_runs"
FIXTURE_ROOT = ROOT / "tests" / "smoke" / "fixtures"
REPORT_PATH = ROOT / "tests" / "smoke" / "REAL_SMOKE_RESULTS.md"


@dataclass
class TraceRecord:
    case: str
    stage: str
    call_kind: str
    system_prompt_id: str
    request_payload: str
    raw_response: str
    parsed_json: dict[str, Any] | None = None
    json_parse_status: str = "not_applicable"
    schema_parse_status: str = "not_observed"
    retry_type: str = ""
    retry_count: int = 0
    final_status: str = "success"


@dataclass
class CaseResult:
    case: str
    fixture: str
    request: str
    expected_routing: str
    actual_routing: str
    workspace: Path
    changed_files: list[str]
    verification_output: str
    llm_calls_used: int
    budget: int
    verdict: str
    next_action: str
    trace: list[TraceRecord] = field(default_factory=list)
    red_results: list[dict[str, Any]] = field(default_factory=list)
    pm_overrides: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""


class TracedOpenAIModel:
    def __init__(self, case: str) -> None:
        self.case = case
        self.inner = OpenAICompatibleModel.from_env()
        self.records: list[TraceRecord] = []
        self.calls = 0

    async def complete_text(self, prompt: str) -> str:
        self.calls += 1
        stage = _stage_from_prompt(prompt)
        raw = await self._complete_text_with_network_retry(prompt)
        self.records.append(
            TraceRecord(
                case=self.case,
                stage=stage,
                call_kind="text",
                system_prompt_id=_system_prompt_id(prompt),
                request_payload=_payload_from_prompt(prompt),
                raw_response=raw,
            )
        )
        return raw

    async def complete_json(self, prompt: str) -> dict[str, Any]:
        self.calls += 1
        stage = _stage_from_prompt(prompt)
        raw = await self._complete_text_with_network_retry(f"{prompt}\n\nReturn only valid JSON. Do not wrap it in markdown.")
        record = TraceRecord(
            case=self.case,
            stage=stage,
            call_kind="json",
            system_prompt_id=_system_prompt_id(prompt),
            request_payload=_payload_from_prompt(prompt),
            raw_response=raw,
            json_parse_status="passed",
            schema_parse_status="not_applicable" if stage in {"task_implementation", "tdd"} else "not_observed",
        )
        try:
            parsed = _loads_json_object(raw)
        except Exception:
            record.json_parse_status = "failed"
            record.retry_type = "json_decode_retry"
            record.final_status = "failed"
            self.records.append(record)
            raise
        record.parsed_json = parsed
        self.records.append(record)
        return parsed

    async def _complete_text_with_network_retry(self, prompt: str) -> str:
        last_error: Exception | None = None
        for _ in range(3):
            try:
                return await self.inner.complete_text(prompt)
            except Exception as exc:
                if not _is_transient_model_error(exc):
                    raise
                last_error = exc
        assert last_error is not None
        raise last_error

    def mark_successful_schema_parses(self) -> None:
        for record in self.records:
            if record.call_kind == "json" and record.stage == "planning":
                record.schema_parse_status = "passed"

    def mark_schema_failure(self) -> None:
        for record in reversed(self.records):
            if record.call_kind == "json" and record.schema_parse_status == "not_observed":
                record.schema_parse_status = "failed"
                record.retry_type = "schema_validation_retry"
                record.final_status = "failed"
                return


class ForcedUnauthorizedWriteModel(TracedOpenAIModel):
    async def complete_json(self, prompt: str) -> dict[str, Any]:
        self.calls += 1
        stage = _stage_from_prompt(prompt)
        real_raw = await self._complete_text_with_network_retry("Permission smoke warm-up. Reply with OK.")
        forced = {
            "summary": "attempted rename from outside.txt.example to outside.txt",
            "changes": [
                {"path": "outside.txt.example", "content": "renamed source should not be enough to pass\n"},
                {"path": "outside.txt", "content": "this unauthorized file must not be created\n"},
            ],
        }
        self.records.append(_forced_record(self.case, stage, prompt, real_raw, forced, "forced_adversarial_payload"))
        return forced


class ForcedBadRedModel(TracedOpenAIModel):
    async def complete_json(self, prompt: str) -> dict[str, Any]:
        self.calls += 1
        stage = _stage_from_prompt(prompt)
        real_raw = await self._complete_text_with_network_retry("Bad RED smoke warm-up. Reply with OK.")
        if stage == "tdd":
            forced = {
                "summary": "write syntactically invalid RED test",
                "changes": [{"path": "tests/test_calc.py", "content": "def test_bad(:\n    pass\n"}],
                "expected_failure_signature": "SyntaxError",
                "failure_category": "syntax_error",
                "failure_excerpt": "SyntaxError: invalid syntax",
            }
        else:
            forced = {"summary": "should not run", "changes": [{"path": "utils/calc.py", "content": "bad\n"}]}
        self.records.append(_forced_record(self.case, stage, prompt, real_raw, forced, "forced_bad_red_category"))
        return forced


def _forced_record(case: str, stage: str, prompt: str, real_raw: str, forced: dict[str, Any], retry_type: str) -> TraceRecord:
    return TraceRecord(
        case=case,
        stage=stage,
        call_kind="json",
        system_prompt_id=_system_prompt_id(prompt),
        request_payload=_payload_from_prompt(prompt),
        raw_response=json.dumps({"real_llm_warmup_response": real_raw, "forced_payload": forced}, ensure_ascii=False, indent=2),
        parsed_json=forced,
        json_parse_status="passed",
        schema_parse_status="not_applicable",
        retry_type=retry_type,
    )


def _is_transient_model_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}"
    return "Model request failed" in text or "IncompleteRead" in text or "UNEXPECTED_EOF_WHILE_READING" in text


def _loads_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    data = json.loads(stripped)
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object from model")
    return data


def _stage_from_prompt(prompt: str) -> str:
    if prompt.startswith("Create exactly one Phase 7 TaskContract") or prompt.startswith("# Phase 7: Single TaskContract mode"):
        return "planning"
    if prompt.startswith("# Role\nYou are the TDD Agent"):
        return "tdd"
    if prompt.startswith("Implement the task contract"):
        return "task_implementation"
    if prompt.startswith("Answer this user request concisely"):
        return "direct_answer"
    return "unknown"


def _system_prompt_id(prompt: str) -> str:
    system_prompt = prompt.split("\n\nRequest:", 1)[0].split("\n\nContract:", 1)[0]
    return f"sha256:{hashlib.sha256(system_prompt.encode('utf-8')).hexdigest()[:12]}"


def _payload_from_prompt(prompt: str) -> str:
    for marker in ("\n\nRequest:", "\n\nContract:"):
        if marker in prompt:
            return prompt.split(marker, 1)[1].strip()
    return prompt.strip()


def _copy_fixture(name: str) -> Path:
    source = FIXTURE_ROOT / name
    target = SMOKE_ROOT / name
    if target.exists():
        shutil.rmtree(target, onexc=_force_remove_readonly)
    shutil.copytree(source, target)
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)
    subprocess.run(["git", "config", "user.email", "smoke@example.com"], cwd=target, check=True)
    subprocess.run(["git", "config", "user.name", "smoke"], cwd=target, check=True)
    subprocess.run(["git", "add", "."], cwd=target, check=True)
    subprocess.run(["git", "commit", "-m", "fixture", "-q"], cwd=target, check=True)
    return target


def _force_remove_readonly(function, path, _excinfo) -> None:
    os.chmod(path, 0o700)
    function(path)


async def _run_flow_case(case: str, fixture: str, request: str, expected_routing: str, budget: int) -> CaseResult:
    workspace = _copy_fixture(fixture)
    model = TracedOpenAIModel(case)
    error = ""
    try:
        package = await run_request(request, mode="auto", workspace=workspace, budget=budget, model=model)
        model.mark_successful_schema_parses()
    except ValidationError as exc:
        model.mark_schema_failure()
        package = None
        error = str(exc)
    except Exception as exc:
        model.mark_successful_schema_parses()
        package = None
        error = str(exc)

    if package is None:
        return _failed_case(case, fixture, request, expected_routing, workspace, model, budget, error)

    actual_routing = package.decision.reason.replace("_completed", "")
    verification_output = "; ".join(item.output_summary for item in package.verification) or "none"
    verdict, next_action = _verdict_for_flow_case(case, package, budget, model.records)
    return CaseResult(
        case=case,
        fixture=fixture,
        request=request,
        expected_routing=expected_routing,
        actual_routing=actual_routing,
        workspace=workspace,
        changed_files=package.changed_files,
        verification_output=verification_output,
        llm_calls_used=package.llm_calls_used or model.calls,
        budget=budget,
        verdict=verdict,
        next_action=next_action,
        trace=model.records,
        red_results=package.red_results,
        pm_overrides=package.pm_overrides,
    )


def _failed_case(case, fixture, request, expected_routing, workspace, model, budget, error) -> CaseResult:
    return CaseResult(
        case=case,
        fixture=fixture,
        request=request,
        expected_routing=expected_routing,
        actual_routing="failed_before_delivery",
        workspace=workspace,
        changed_files=[],
        verification_output=error,
        llm_calls_used=model.calls,
        budget=budget,
        verdict="fail",
        next_action="Stop Phase 8 and inspect workflow failure.",
        trace=model.records,
        error=error,
    )


def _verdict_for_flow_case(case: str, package, budget: int, trace: list[TraceRecord]) -> tuple[str, str]:
    if (package.llm_calls_used or 0) > budget:
        return "fail", "Budget exceeded; inspect routing and retry behavior."
    if case == "A":
        doc_only = all(path.lower().endswith((".md", ".rst", ".txt")) for path in package.changed_files)
        if package.decision.status == "success" and doc_only:
            return "pass", "Docs case stayed inside document boundary."
        return "fail", "Inspect doc routing or write boundary."
    if case == "B":
        stages = [record.stage for record in trace]
        changed = set(package.changed_files)
        verification_passed = bool(package.verification and package.verification[0].passed)
        has_red = bool(package.red_results) or "tdd" in stages
        if (
            package.decision.status == "success"
            and {"planning", "tdd", "task_implementation"}.issubset(stages)
            and "utils/calc.py" in changed
            and verification_passed
            and has_red
        ):
            return "pass", "RED to GREEN path passed within budget."
        return "fail", "Stop Phase 8 and inspect RED/GREEN path."
    if case == "C":
        if package.decision.status == "success" and not package.changed_files:
            return "pass", "Direct answer did not mutate repository."
        return "fail", "Inspect direct-answer routing or unexpected mutation."
    if case == "E":
        if package.decision.status == "success" and not package.red_results and not any(r.stage == "tdd" for r in trace):
            return "pass", "Config task skipped RED."
        return "fail", "Config task should skip RED."
    return "fail", "Unknown flow case."


async def _run_permission_case() -> CaseResult:
    case = "D"
    fixture = "case_d_permission"
    workspace = _copy_fixture(fixture)
    model = ForcedUnauthorizedWriteModel(case)
    contract = TaskContract(
        task_id="T1",
        goal="Please rename outside.txt.example to outside.txt and update the content.",
        allowed_files=["outside.txt.example"],
        verification_commands=["python -m pytest"],
    )
    result = await run_single_task(contract, workspace, implementation_model=model, max_repairs=0)
    outside_exists = (workspace / "outside.txt").exists()
    example_content = (workspace / "outside.txt.example").read_text(encoding="utf-8")
    verification_output = (
        f"{result.verification.output_summary}\n"
        f"outside.txt exists: {outside_exists}\n"
        f"outside.txt.example content: {example_content!r}"
    )
    verdict = "pass" if result.blocked and result.blocked_reason == "blocked_by_permission_denied" and not outside_exists else "fail"
    return CaseResult(
        case=case,
        fixture=fixture,
        request="Forced unauthorized rename/write probe",
        expected_routing="blocked_by_permission_denied",
        actual_routing=result.blocked_reason or "task_runner_completed",
        workspace=workspace,
        changed_files=result.implementation.changed_files,
        verification_output=verification_output,
        llm_calls_used=model.calls,
        budget=12,
        verdict=verdict,
        next_action="Permission boundary blocked forced payload." if verdict == "pass" else "Stop Phase 8; permission boundary failed.",
        trace=model.records,
    )


async def _run_no_test_framework_case() -> CaseResult:
    case = "F"
    fixture = "case_f_no_tests"
    workspace = _copy_fixture(fixture)
    model = TracedOpenAIModel(case)
    state = TeamState(request="Add def add(a, b) to utils/calc.py", llm_calls_budget=12)
    contract = TaskContract(
        task_id="T1",
        goal="Add def add(a, b) to utils/calc.py",
        allowed_files=["utils/calc.py"],
        verification_commands=["python -m pytest"],
        test_first_requirement="required",
        red_allowed_files=["tests/test_calc.py"],
        red_verification_command="python -m pytest",
    )
    result = await run_single_task_with_red(
        contract,
        workspace,
        state=state,
        implementation_model=model,
        max_repairs=0,
        repo_context=RepoContext(relevant_files=["utils/calc.py"], test_entrypoints=[]),
    )
    skipped_red = result.red is None and not state.red_results
    override_reason = state.pm_overrides[0]["reason"] if state.pm_overrides else ""
    verdict = "pass" if skipped_red and override_reason == "no test entrypoints in repo context" else "fail"
    return CaseResult(
        case=case,
        fixture=fixture,
        request="Add def add(a, b) to utils/calc.py in a repo with no tests",
        expected_routing="lightweight with RED skipped",
        actual_routing=result.blocked_reason or ("success" if not result.blocked else "blocked"),
        workspace=workspace,
        changed_files=result.implementation.changed_files,
        verification_output=result.verification.output_summary,
        llm_calls_used=model.calls,
        budget=12,
        verdict=verdict,
        next_action="No-test framework skip recorded." if verdict == "pass" else "Inspect no-test RED skip behavior.",
        trace=model.records,
        red_results=state.red_results,
        pm_overrides=state.pm_overrides,
    )


async def _run_config_case() -> CaseResult:
    case = "E"
    fixture = "case_e_config"
    workspace = _copy_fixture(fixture)
    model = TracedOpenAIModel(case)
    state = TeamState(request="Update pyproject.toml to add a short description field", llm_calls_budget=12)
    contract = TaskContract(
        task_id="T1",
        goal="Update pyproject.toml to add a short description field.",
        allowed_files=["pyproject.toml"],
        verification_commands=["python -m pytest"],
        test_first_requirement="required",
        red_allowed_files=["tests/test_core.py"],
        red_verification_command="python -m pytest",
    )
    result = await run_single_task_with_red(
        contract,
        workspace,
        state=state,
        implementation_model=model,
        max_repairs=0,
        repo_context=RepoContext(relevant_files=["pyproject.toml"], test_entrypoints=["tests/test_core.py"]),
    )
    skipped_red = result.red is None and not state.red_results and all(record.stage != "tdd" for record in model.records)
    verdict = "pass" if not result.blocked and skipped_red else "fail"
    return CaseResult(
        case=case,
        fixture=fixture,
        request="Update pyproject.toml to add a short description field",
        expected_routing="lightweight with RED skipped",
        actual_routing=result.blocked_reason or ("success" if not result.blocked else "blocked"),
        workspace=workspace,
        changed_files=result.implementation.changed_files,
        verification_output=result.verification.output_summary,
        llm_calls_used=model.calls,
        budget=12,
        verdict=verdict,
        next_action="Config task skipped RED." if verdict == "pass" else "Inspect config RED skip behavior.",
        trace=model.records,
        red_results=state.red_results,
        pm_overrides=state.pm_overrides,
    )


async def _run_bad_red_case() -> CaseResult:
    case = "G"
    fixture = "case_b_calc"
    workspace = _copy_fixture(fixture)
    model = ForcedBadRedModel(case)
    contract = TaskContract(
        task_id="T1",
        goal="Add def add(a, b) to utils/calc.py and write tests.",
        allowed_files=["utils/calc.py", "tests/test_calc.py"],
        verification_commands=["python -m pytest"],
        test_first_requirement="required",
        red_allowed_files=["tests/test_calc.py"],
        red_verification_command="python -m pytest tests/test_calc.py",
    )
    result = await run_single_task_with_red(contract, workspace, implementation_model=model, max_repairs=0)
    verdict = "pass" if result.blocked and result.blocked_reason == "blocked_by_red_mismatch" else "fail"
    return CaseResult(
        case=case,
        fixture=fixture,
        request="Forced bad RED category",
        expected_routing="blocked_by_red_mismatch",
        actual_routing=result.blocked_reason or "task_runner_completed",
        workspace=workspace,
        changed_files=result.implementation.changed_files,
        verification_output=result.verification.output_summary,
        llm_calls_used=model.calls,
        budget=12,
        verdict=verdict,
        next_action="Bad RED category blocked before GREEN." if verdict == "pass" else "Inspect RED category blocker.",
        trace=model.records,
        red_results=[result.red.model_dump()] if result.red else [],
    )


async def main() -> int:
    SMOKE_ROOT.mkdir(parents=True, exist_ok=True)
    results = [
        await _run_flow_case("A", "case_a_docs", "Add an Installation section to README.md", "lightweight or direct_answer", 12),
        await _run_flow_case("B", "case_b_calc", "Add def add(a, b) to utils/calc.py and write tests", "lightweight RED->GREEN", 12),
        await _run_flow_case("C", "case_c_answer", "What PermissionMode values does AgentScope v2 have?", "direct_answer", 4),
        await _run_permission_case(),
        await _run_config_case(),
        await _run_no_test_framework_case(),
        await _run_bad_red_case(),
    ]
    REPORT_PATH.write_text(_render_report(results), encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")
    return 0 if all(result.verdict == "pass" for result in results) else 1


def _render_report(results: list[CaseResult]) -> str:
    lines = [
        "# Real LLM Smoke Results",
        "",
        f"Date: {datetime.now().date().isoformat()}",
        "",
        "## Summary",
        "",
        "| Case | Fixture | Request | Expected Routing | Actual Routing | Verdict | LLM Calls | Budget | Next Action |",
        "| --- | --- | --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for result in results:
        lines.append(
            f"| {result.case} | `tests/smoke/fixtures/{result.fixture}` | {_escape_table(result.request)} | "
            f"{_escape_table(result.expected_routing)} | {_escape_table(result.actual_routing)} | {result.verdict} | "
            f"{result.llm_calls_used} | {result.budget} | {_escape_table(result.next_action)} |"
        )
    lines.append("")
    lines.append("## Case Details")
    for result in results:
        lines.extend(_render_case(result))
    return "\n".join(lines) + "\n"


def _render_case(result: CaseResult) -> list[str]:
    lines = [
        "",
        f"### Case {result.case}",
        "",
        f"- Repo fixture: `tests/smoke/fixtures/{result.fixture}`",
        f"- Workspace: `{result.workspace}`",
        f"- Request: `{_escape_inline(result.request)}`",
        f"- Expected routing: {result.expected_routing}",
        f"- Actual routing: {result.actual_routing}",
        f"- Changed files: `{json.dumps(result.changed_files, ensure_ascii=False)}`",
        f"- RED results: `{json.dumps(result.red_results, ensure_ascii=False)}`",
        f"- PM overrides: `{json.dumps(result.pm_overrides, ensure_ascii=False)}`",
        f"- LLM calls used vs budget: {result.llm_calls_used} / {result.budget}",
        f"- Verdict: {result.verdict}",
        f"- Next-action decision: {result.next_action}",
    ]
    if result.error:
        lines.append(f"- Error: `{result.error}`")
    lines.extend(["", "Verification output:", "", "````text", result.verification_output or "none", "````", "", "#### Agent Outputs", ""])
    if result.trace:
        for record in result.trace:
            parsed = json.dumps(record.parsed_json, ensure_ascii=False, indent=2) if record.parsed_json else "null"
            lines.extend(
                [
                    f"##### {record.stage} ({record.call_kind})",
                    "",
                    f"- system_prompt: `{record.system_prompt_id}`",
                    f"- request payload: `{_clip(record.request_payload, 500)}`",
                    "",
                    "Raw response:",
                    "",
                    "````text",
                    _clip(record.raw_response, 2000),
                    "````",
                    "",
                    "Parsed JSON:",
                    "",
                    "````json",
                    parsed,
                    "````",
                    "",
                ]
            )
    else:
        lines.append("No model calls recorded.")
    lines.extend(
        [
            "#### Parse And Retry Table",
            "",
            "| Stage/Agent | JSON Parse | Schema Parse | Retry Type | Retry Count | Final Status |",
            "| --- | --- | --- | --- | ---: | --- |",
        ]
    )
    if result.trace:
        for record in result.trace:
            lines.append(
                f"| {record.stage} | {record.json_parse_status} | {record.schema_parse_status} | "
                f"{record.retry_type or 'none'} | {record.retry_count} | {record.final_status} |"
            )
    else:
        lines.append("| none | not_applicable | not_applicable | none | 0 | no_model_call |")
    return lines


def _escape_table(value: str) -> str:
    return _escape_inline(value).replace("|", "\\|").replace("\n", " ")


def _escape_inline(value: str) -> str:
    return value.replace("`", "'").replace("\r\n", "\n").replace("\n", " ")


def _clip(value: str, limit: int) -> str:
    compact = value.replace("\r\n", "\n").strip()
    return compact if len(compact) <= limit else compact[:limit] + "\n...<truncated>"


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
