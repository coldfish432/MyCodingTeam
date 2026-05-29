"""Review-only workflow."""

from __future__ import annotations

import re
from pathlib import Path

import my_coding_team.agents.context_scout  # noqa: F401
import my_coding_team.rooms.review_room  # noqa: F401
from my_coding_team.agents.delivery import build_delivery_package
from my_coding_team.core.registry import ROOMS, STEPS
from my_coding_team.core.step import StepContext
from my_coding_team.orchestration.review_input_materializer import materialize_review_input
from my_coding_team.orchestration.workspace_manager import prepare_workspace_readonly
from my_coding_team.schemas.room_inputs import ReviewRoomInput
from my_coding_team.schemas.review import ReviewOnlyReport
from my_coding_team.schemas.step_inputs import ContextScoutInput
from my_coding_team.schemas.workflow import ReviewOnlyInput, TeamState


async def run_review_only(
    state: TeamState,
    *,
    workspace_root: str | Path,
    model=None,
    pasted_content: str | None = None,
) -> object:
    """Run a read-only review and return a DeliveryPackage."""
    state.current_phase = "workspace_prepared"
    workspace = prepare_workspace_readonly(workspace_root)
    state.workspace = workspace

    input_spec = _resolve_review_only_input(state, pasted_content=pasted_content)
    state.review_only_input = input_spec.model_dump()

    repo_context = None
    ctx = StepContext(model=model, workspace_root=workspace.root)
    if input_spec.input_kind != "pasted_text":
        state.current_phase = "context_collected"
        repo_context = await STEPS["context_scout"].run(
            ContextScoutInput(
                request=f"Read-only review context for {input_spec.input_kind}",
                workspace=workspace,
            ),
            ctx,
        )
        state.repo_context = repo_context

    target_blob = await materialize_review_input(input_spec, workspace)

    state.current_phase = "reviewing_readonly"
    report = await ROOMS["review_room"].execute(
        ReviewRoomInput(
            scope="review_only",
            review_only_input=input_spec.model_dump(),
            review_target_blob=target_blob,
            repo_context=repo_context.model_dump() if repo_context else None,
        ),
        ctx,
    )
    if model is not None:
        state.llm_calls_used += 1
    state.final_review = report.model_dump()

    state.current_phase = "delivered"
    summary = _summary_from_report(report)
    return build_delivery_package(
        state,
        status="success",
        reason="review_only_completed",
        summary=summary,
        changed_files=[],
        review=report,
        risks=[*report.should_fix, *report.nice_to_have],
    )


def _resolve_review_only_input(state: TeamState, *, pasted_content: str | None = None) -> ReviewOnlyInput:
    if state.review_only_input:
        data = dict(state.review_only_input)
        if pasted_content and data.get("input_kind") == "pasted_text":
            data["pasted_content"] = pasted_content
        return ReviewOnlyInput.model_validate(data)

    if pasted_content is not None:
        return ReviewOnlyInput(
            input_kind="pasted_text",
            pasted_content=pasted_content,
            pasted_language_hint=_language_hint_from_request(state.request),
        )

    suggested = state.route_decision.suggested_review_input if state.route_decision else None
    if suggested:
        data = dict(suggested)
        if data.get("input_kind") == "pasted_text":
            data["pasted_content"] = _extract_pasted_content(state.request)
        try:
            return ReviewOnlyInput.model_validate(data)
        except Exception:
            pass

    files = _extract_review_files(state.request)
    if files:
        return ReviewOnlyInput(input_kind="file_list", files_to_review=files)
    if _looks_like_pasted_code(state.request):
        return ReviewOnlyInput(
            input_kind="pasted_text",
            pasted_content=_extract_pasted_content(state.request),
            pasted_language_hint=_language_hint_from_request(state.request),
        )
    return ReviewOnlyInput(input_kind="workspace_diff", diff_base="HEAD")


def _extract_review_files(request: str) -> list[str]:
    matches = re.findall(
        r"(?<![\w.-])([\w./\\-]+\.(?:py|md|toml|json|yaml|yml|txt|rst|ini|cfg))(?![\w.-])",
        request,
    )
    seen: set[str] = set()
    files: list[str] = []
    for match in matches:
        normalized = match.replace("\\", "/").strip(".,;:)")
        if normalized and normalized not in seen:
            seen.add(normalized)
            files.append(normalized)
    return files


def _looks_like_pasted_code(request: str) -> bool:
    return "```" in request or any(marker in request for marker in ("def ", "class ", "function ", "const ", "let "))


def _extract_pasted_content(request: str) -> str:
    fenced = re.search(r"```(?:\w+)?\s*(.*?)```", request, flags=re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    return request.strip()


def _language_hint_from_request(request: str) -> str | None:
    fenced = re.search(r"```(\w+)", request)
    if fenced:
        return fenced.group(1)
    if "def " in request or "class " in request:
        return "python"
    if "function " in request or "const " in request or "let " in request:
        return "javascript"
    return None


def _summary_from_report(report: ReviewOnlyReport) -> str:
    must_count = len(report.finding.must_fix)
    should_count = len(report.should_fix)
    nice_count = len(report.nice_to_have)
    return (
        f"Review-only report for {report.input_summary}: "
        f"{must_count} must_fix, {should_count} should_fix, {nice_count} nice_to_have."
    )
