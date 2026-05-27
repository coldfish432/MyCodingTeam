import pytest
from pydantic import ValidationError

from my_coding_team.schemas import (
    AgentOutput,
    DeliveryPackage,
    Evidence,
    FinalReviewReport,
    FinishDecision,
    ReviewFinding,
    RouteDecision,
    TaskContract,
    TaskReviewResult,
    TeamState,
    VerificationResult,
    WorkspaceRecord,
)


def _first_loc(exc: ValidationError):
    return exc.errors()[0]["loc"]


def test_team_state_round_trips():
    state = TeamState(
        request="Add docs",
        workflow="lightweight",
        route_decision=RouteDecision(
            workflow="lightweight",
            risk="low",
            confidence=0.82,
            rationale="small docs change",
        ),
        workspace=WorkspaceRecord(
            root="D:/Mycode/myCodingTeam",
            is_git=False,
            dirty_files=["README.md"],
        ),
        llm_calls_budget=0,
    )

    restored = TeamState.model_validate_json(state.model_dump_json())

    assert restored == state
    assert restored.route_decision is not None
    assert restored.route_decision.workflow == "lightweight"


def test_team_state_rejects_budget_overrun():
    with pytest.raises(ValidationError) as exc_info:
        TeamState(request="x", llm_calls_used=2, llm_calls_budget=1)

    assert "llm_calls_used must be <= llm_calls_budget" in str(exc_info.value)


def test_route_decision_rejects_bad_workflow_with_field_location():
    with pytest.raises(ValidationError) as exc_info:
        RouteDecision(workflow="unknown", risk="low", confidence=0.5)

    assert _first_loc(exc_info.value) == ("workflow",)


def test_route_decision_rejects_bad_risk_with_field_location():
    with pytest.raises(ValidationError) as exc_info:
        RouteDecision(workflow="direct_answer", risk="critical", confidence=0.5)

    assert _first_loc(exc_info.value) == ("risk",)


def test_confidence_bounds_are_enforced_with_field_location():
    with pytest.raises(ValidationError) as exc_info:
        AgentOutput(agent_name="router", status="success", confidence=1.01)

    assert _first_loc(exc_info.value) == ("confidence",)


def test_task_contract_requires_allowed_files():
    with pytest.raises(ValidationError) as exc_info:
        TaskContract(task_id="T1", objective="Edit file", allowed_files=[])

    assert _first_loc(exc_info.value) == ("allowed_files",)
    assert "allowed_files must not be empty" in str(exc_info.value)


def test_review_finding_blocks_approval_when_must_fix_present():
    with pytest.raises(ValidationError) as exc_info:
        ReviewFinding(
            finding_id="R1",
            title="Fix missing validation",
            approval=True,
            must_fix=["Add field validation"],
            evidence=[Evidence(path="my_coding_team/schemas/task.py", line=1)],
        )

    assert "approval=false" in str(exc_info.value)


def test_review_finding_requires_evidence_for_must_fix():
    with pytest.raises(ValidationError) as exc_info:
        ReviewFinding(
            finding_id="R1",
            title="Fix missing validation",
            approval=False,
            must_fix=["Add field validation"],
        )

    assert "requires evidence" in str(exc_info.value)


def test_task_review_result_cannot_approve_unresolved_must_fix():
    finding = ReviewFinding(
        finding_id="R1",
        title="Fix bug",
        approval=False,
        must_fix=["Fix bug"],
        evidence=[Evidence(path="tests/test_schemas.py", line=1)],
    )

    with pytest.raises(ValidationError) as exc_info:
        TaskReviewResult(task_id="T1", approval=True, findings=[finding])

    assert "cannot approve unresolved must_fix" in str(exc_info.value)


def test_delivery_package_composes_review_and_verification():
    package = DeliveryPackage(
        request="Add docs",
        decision=FinishDecision(status="success", reason="verified"),
        changed_files=["README.md"],
        verification=[
            VerificationResult(
                task_id="T1",
                passed=True,
                commands=["pytest"],
                output_summary="passed",
            )
        ],
        review=FinalReviewReport(approval=True, summary="no findings"),
    )

    assert package.decision.status == "success"
    assert package.verification[0].passed is True
