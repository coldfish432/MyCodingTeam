import pytest
from pydantic import ValidationError

from my_coding_team.schemas.common import Evidence
from my_coding_team.schemas.delivery import DeliveryPackage, FinishDecision
from my_coding_team.schemas.review import ReviewFinding, ReviewOnlyReport
from my_coding_team.schemas.workflow import ReviewOnlyInput


def test_file_list_requires_files():
    with pytest.raises(ValidationError):
        ReviewOnlyInput(input_kind="file_list")


def test_pasted_text_requires_content():
    with pytest.raises(ValidationError):
        ReviewOnlyInput(input_kind="pasted_text")


def test_workspace_diff_defaults_are_valid():
    value = ReviewOnlyInput(input_kind="workspace_diff")

    assert value.diff_base is None
    assert value.diff_target is None


def test_review_only_report_accepts_empty_hint():
    report = ReviewOnlyReport(
        finding=ReviewFinding(finding_id="clean", title="No issues"),
        review_target_kind="file_list",
        input_summary="src/app.py (1 file)",
    )

    assert report.next_step_hint is None


def test_review_only_delivery_cannot_report_changed_files():
    with pytest.raises(ValidationError):
        DeliveryPackage(
            request="review",
            decision=FinishDecision(status="success", reason="done"),
            workflow_kind="review_only",
            changed_files=["src/app.py"],
        )


def test_non_review_delivery_can_report_changed_files():
    package = DeliveryPackage(
        request="fix",
        decision=FinishDecision(status="success", reason="done"),
        workflow_kind="lightweight",
        changed_files=["src/app.py"],
    )

    assert package.changed_files == ["src/app.py"]


def test_review_finding_must_fix_still_requires_evidence():
    with pytest.raises(ValidationError):
        ReviewFinding(
            finding_id="bug",
            title="Bug",
            approval=False,
            must_fix=["Fix it"],
        )

    finding = ReviewFinding(
        finding_id="bug",
        title="Bug",
        approval=False,
        must_fix=["Fix it"],
        evidence=[Evidence(path="src/app.py", note="bug")],
    )
    assert finding.must_fix
