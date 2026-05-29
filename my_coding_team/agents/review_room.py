"""ReviewRoom internals for task, final, and review-only scopes."""

from __future__ import annotations

import json

from my_coding_team.orchestration.review_input_materializer import summarize_review_input
from my_coding_team.runtime.middleware import parse_schema
from my_coding_team.runtime.prompts import load_prompt
from my_coding_team.schemas.common import Evidence
from my_coding_team.schemas.review import FinalReviewReport, ReviewFinding, ReviewOnlyReport, TaskReviewResult
from my_coding_team.schemas.task import (
    ImplementationResult,
    RedResult,
    TaskContract,
    TaskRunResult,
    VerificationResult,
)
from my_coding_team.schemas.workflow import ProductBrief, RepoContext, ReviewOnlyInput


async def _review_task(
    contract: TaskContract | None,
    implementation: ImplementationResult | None,
    verification: VerificationResult | None,
    *,
    red: RedResult | None = None,
    model=None,
) -> TaskReviewResult:
    """Review a single task result."""
    if contract is None or implementation is None or verification is None:
        return TaskReviewResult(
            task_id="unknown",
            approval=False,
            summary="missing required inputs for task review",
            findings=[
                ReviewFinding(
                    finding_id="missing_inputs",
                    title="Missing required inputs",
                    severity="high",
                    approval=False,
                    must_fix=["Provide contract, implementation, and verification for task review."],
                    evidence=[Evidence(path=".", note="inputs missing")],
                ),
            ],
        )

    findings: list[ReviewFinding] = []
    if not verification.passed:
        findings.append(
            ReviewFinding(
                finding_id="verification_failed",
                title="Verification did not pass",
                severity="high",
                approval=False,
                must_fix=["Fix failing or missing verification before delivery."],
                evidence=[Evidence(path=".", note=verification.output_summary or "verification failed")],
            ),
        )
    unauthorized = [path for path in implementation.changed_files if path not in contract.allowed_files]
    if unauthorized:
        findings.append(
            ReviewFinding(
                finding_id="unauthorized_files",
                title="Implementation changed files outside allowed_files",
                severity="high",
                approval=False,
                must_fix=[f"Remove unauthorized changes: {', '.join(unauthorized)}"],
                evidence=[Evidence(path=unauthorized[0], note="changed outside contract")],
            ),
        )
    if red is not None and red.red_type == "test":
        if not red.files_changed:
            findings.append(
                ReviewFinding(
                    finding_id="red_test_missing_files",
                    title="RED test did not write a test file",
                    severity="high",
                    approval=False,
                    must_fix=["Fix RED test: no test file was written."],
                    evidence=[Evidence(path=".", note=red.actual_output or "RED test file missing")],
                ),
            )
        if red.failure_category in {"syntax_error", "collection_error", "other"}:
            findings.append(
                ReviewFinding(
                    finding_id="red_test_quality",
                    title="RED test failed for an unacceptable reason",
                    severity="high",
                    approval=False,
                    must_fix=["Fix RED test quality before delivery."],
                    evidence=[
                        Evidence(
                            path=red.files_changed[0] if red.files_changed else ".",
                            note=red.failure_excerpt or red.actual_output or red.failure_category or "invalid RED",
                        )
                    ],
                ),
            )
    approval = not any(finding.must_fix for finding in findings)
    return TaskReviewResult(
        task_id=contract.task_id,
        approval=approval,
        summary="approved" if approval else "must_fix findings remain",
        findings=findings,
    )


async def _review_only(
    *,
    input_spec: ReviewOnlyInput,
    target_blob: str,
    repo_context: RepoContext | None,
    model=None,
) -> ReviewOnlyReport:
    """Run read-only review with deterministic fallback."""
    if model is None:
        return _review_only_deterministic(input_spec, target_blob, fallback_reason="LLM not provided")

    prompt = _build_review_only_prompt(input_spec, target_blob, repo_context)
    try:
        payload = await model.complete_json(prompt)
        finding = parse_schema(ReviewFinding, payload)
        return ReviewOnlyReport(
            finding=finding,
            review_target_kind=input_spec.input_kind,
            input_summary=summarize_review_input(input_spec, target_blob),
            next_step_hint=build_next_step_hint(input_spec, finding),
        )
    except Exception as exc:
        return _review_only_deterministic(input_spec, target_blob, fallback_reason=str(exc))


def _build_review_only_prompt(
    input_spec: ReviewOnlyInput,
    target_blob: str,
    repo_context: RepoContext | None,
) -> str:
    payload = {
        "input_kind": input_spec.input_kind,
        "input_summary": summarize_review_input(input_spec, target_blob),
        "user_focus_hint": input_spec.user_focus_hint,
        "repo_context": repo_context.model_dump() if repo_context else None,
        "review_target_blob": target_blob,
    }
    return f"{load_prompt('review_room_readonly')}\n\n```json\n{json.dumps(payload, indent=2)}\n```"


def _review_only_deterministic(
    input_spec: ReviewOnlyInput,
    target_blob: str,
    *,
    fallback_reason: str,
) -> ReviewOnlyReport:
    """Return a non-blocking report when LLM review is unavailable."""
    finding = ReviewFinding(
        finding_id="review_unavailable",
        title="Review unavailable",
        severity="low",
        approval=True,
        must_fix=[],
        evidence=[Evidence(path=".", note=fallback_reason[:300])] if fallback_reason else [],
    )
    return ReviewOnlyReport(
        finding=finding,
        review_target_kind=input_spec.input_kind,
        input_summary=summarize_review_input(input_spec, target_blob),
        should_fix=[],
        nice_to_have=[],
        next_step_hint=None,
    )


def build_next_step_hint(input_spec: ReviewOnlyInput, finding: ReviewFinding) -> str | None:
    """Generate user guidance for must_fix items without starting a write workflow."""
    if not finding.must_fix:
        return None
    count = len(finding.must_fix)
    item_word = "item" if count == 1 else "items"
    if input_spec.input_kind == "pasted_text":
        return (
            f"Found {count} must_fix {item_word}. To fix: paste the content into a file in your repo, "
            'then run: my-coding-team run "fix the issues in <file>"'
        )
    if input_spec.input_kind == "workspace_diff":
        target = "the changed files"
    else:
        target = ", ".join(input_spec.files_to_review[:3])
        if len(input_spec.files_to_review) > 3:
            target += " ..."
    return f'Found {count} must_fix {item_word}. To fix: my-coding-team run "fix the issues in {target}"'


async def _review_final(
    brief: ProductBrief | None,
    task_results: list[TaskRunResult] | None,
    final_verification: VerificationResult | None,
    *,
    model=None,
) -> FinalReviewReport:
    """Run final review with LLM when available and deterministic fallback otherwise."""
    if model is None:
        return _review_final_deterministic(brief, task_results, final_verification)

    prompt = load_prompt("review_room_final")
    input_text = _build_final_review_input(brief, task_results, final_verification)
    full_prompt = f"{prompt}\n\n{input_text}"

    try:
        payload = await model.complete_json(full_prompt)
        findings_data = payload.get("findings", [])
        approval = payload.get("approval", not findings_data)
        summary = payload.get("summary", "")

        findings = []
        for fd in findings_data:
            evidence_list = []
            for evidence in fd.get("evidence", []):
                if isinstance(evidence, dict):
                    evidence_list.append(Evidence(path=evidence.get("path", "."), note=evidence.get("note", "")))
                elif isinstance(evidence, str):
                    evidence_list.append(Evidence(path=".", note=evidence))

            findings.append(
                ReviewFinding(
                    finding_id=fd.get("finding_id", "final"),
                    title=fd.get("title", ""),
                    severity=fd.get("severity", "medium"),
                    approval=fd.get("approval", True),
                    must_fix=fd.get("must_fix", []),
                    evidence=evidence_list,
                    file_path=fd.get("file_path"),
                )
            )

        for finding in findings:
            _validate_must_fix_has_file_evidence(finding)

        findings = _add_structural_checks(findings, task_results, final_verification)
        residual_risks = payload.get("residual_risks", [])
        final_approval = approval and not any(f.must_fix for f in findings)

        return FinalReviewReport(
            approval=final_approval,
            summary=summary or ("Final review passed" if final_approval else "Final review found blocking issues"),
            findings=findings,
            residual_risks=residual_risks,
        )
    except Exception:
        return _review_final_deterministic(brief, task_results, final_verification)


def _build_final_review_input(
    brief: ProductBrief | None,
    task_results: list[TaskRunResult] | None,
    final_verification: VerificationResult | None,
) -> str:
    """Build structured input for final review."""
    payload = {
        "product_brief": brief.model_dump() if brief else None,
        "task_results": [
            {
                "task_id": result.task_id,
                "status": result.status,
                "files_changed": result.implementation.changed_files if result.implementation else [],
                "summary": result.implementation.summary if result.implementation else None,
                "verification_passed": result.verification.passed if result.verification else False,
            }
            for result in (task_results or [])
        ],
        "final_verification": final_verification.model_dump() if final_verification else None,
    }

    return (
        "Review the following cumulative work against the ProductBrief.\n\n"
        f"```json\n{json.dumps(payload, indent=2, ensure_ascii=False)}\n```\n\n"
        "Return a FinalReviewReport JSON object. No other text.\n"
        "Each finding in the findings array must include:\n"
        "- finding_id, title, severity, approval, must_fix (list of strings)\n"
        "- evidence: list of {path, note} dicts. Each must_fix item MUST have at least one file-path evidence\n"
        "- file_path: optional file path for the finding\n"
        "Also set approval=true only if must_fix is empty, and include residual_risks list."
    )


def _validate_must_fix_has_file_evidence(finding: ReviewFinding) -> None:
    """Require file-level evidence for must_fix findings."""
    if not finding.must_fix:
        return

    file_paths = [
        evidence.path
        for evidence in finding.evidence
        if evidence.path and evidence.path != "." and ("/" in evidence.path or "\\" in evidence.path or "." in evidence.path)
    ]
    if not file_paths:
        raise ValueError(
            f"Finding '{finding.finding_id}': must_fix requires at least one file-level "
            f"evidence entry; got evidence={finding.evidence}"
        )


def _add_structural_checks(
    findings: list[ReviewFinding],
    task_results: list[TaskRunResult] | None,
    final_verification: VerificationResult | None,
) -> list[ReviewFinding]:
    """Add hard structural checks the LLM may omit."""
    existing_ids = {finding.finding_id for finding in findings}

    if final_verification and not final_verification.passed and "final_verification_failed" not in existing_ids:
        findings.append(
            ReviewFinding(
                finding_id="final_verification_failed",
                title="Final verification did not pass",
                severity="high",
                approval=False,
                must_fix=["Final verification must pass before delivery."],
                evidence=[Evidence(path=".", note=final_verification.output_summary or "verification failed")],
            )
        )

    if task_results:
        for task_result in task_results:
            finding_id = f"task_{task_result.task_id}_not_completed"
            if task_result.status != "completed" and finding_id not in existing_ids:
                findings.append(
                    ReviewFinding(
                        finding_id=finding_id,
                        title=f"Task {task_result.task_id} did not complete",
                        severity="high",
                        approval=False,
                        must_fix=[f"Task {task_result.task_id} status: {task_result.status}"],
                        evidence=[Evidence(path=".", note=f"task {task_result.task_id} blocked")],
                    )
                )

    return findings


def _review_final_deterministic(
    brief: ProductBrief | None,
    task_results: list[TaskRunResult] | None,
    final_verification: VerificationResult | None,
) -> FinalReviewReport:
    """Deterministic final review fallback."""
    findings: list[ReviewFinding] = []
    residual_risks: list[str] = []

    if final_verification is None or not final_verification.passed:
        findings.append(
            ReviewFinding(
                finding_id="final_verification_failed",
                title="Final verification did not pass",
                severity="high",
                approval=False,
                must_fix=["Final verification must pass before delivery."],
                evidence=[
                    Evidence(
                        path=".",
                        note=final_verification.output_summary if final_verification else "no final verification",
                    )
                ],
            )
        )

    if task_results:
        for task_result in task_results:
            if task_result.status != "completed":
                findings.append(
                    ReviewFinding(
                        finding_id=f"task_{task_result.task_id}_not_completed",
                        title=f"Task {task_result.task_id} did not complete",
                        severity="high",
                        approval=False,
                        must_fix=[f"Task {task_result.task_id} status: {task_result.status}"],
                        evidence=[Evidence(path=".", note=f"task {task_result.task_id} blocked")],
                    )
                )

    if brief and brief.acceptance_criteria and not (final_verification and final_verification.passed):
        residual_risks.append("acceptance_criteria not independently verified")

    approval = not any(finding.must_fix for finding in findings)
    return FinalReviewReport(
        approval=approval,
        summary="Final review passed" if approval else "Final review found blocking issues",
        findings=findings,
        residual_risks=residual_risks,
    )
