import pytest
from pydantic import ValidationError

from my_coding_team.orchestration.task_runner import verify_red
from my_coding_team.schemas.task import RedResult


def test_verify_red_allows_skip_with_reason():
    assert verify_red(RedResult(task_id="T1", red_type="skip", skip_reason="docs only")) == (True, None)


def test_verify_red_rejects_skip_without_reason():
    ok, reason = verify_red(RedResult(task_id="T1", red_type="skip"))

    assert ok is False
    assert reason == "skip without reason"


def test_verify_red_requires_category_for_test_result():
    with pytest.raises(ValidationError, match="failure_category is required"):
        RedResult(task_id="T1", actual_output="AssertionError")


def test_verify_red_rejects_missing_signature():
    ok, reason = verify_red(RedResult(task_id="T1", actual_output="AssertionError", failure_category="assertion"))

    assert ok is False
    assert "missing expected_failure_signature" in reason


def test_verify_red_rejects_missing_output():
    ok, reason = verify_red(RedResult(task_id="T1", expected_failure_signature="AssertionError", failure_category="assertion"))

    assert ok is False
    assert "missing actual_output" in reason


def test_verify_red_rejects_signature_without_meaningful_tokens():
    ok, reason = verify_red(
        RedResult(task_id="T1", expected_failure_signature="oh", actual_output="oh", failure_category="assertion")
    )

    assert ok is False
    assert "no meaningful tokens" in reason


def test_verify_red_rejects_token_mismatch():
    ok, reason = verify_red(
        RedResult(
            task_id="T1",
            expected_failure_signature="AssertionError",
            actual_output="NameError: missing symbol",
            failure_category="assertion",
        )
    )

    assert ok is False
    assert "missing tokens" in reason


def test_verify_red_accepts_token_match():
    ok, reason = verify_red(
        RedResult(
            task_id="T1",
            expected_failure_signature="AssertionError expected 42",
            actual_output="E AssertionError: expected 42 but got 0",
            failure_category="assertion",
        )
    )

    assert ok is True
    assert reason is None


def test_verify_red_is_case_insensitive():
    ok, reason = verify_red(
        RedResult(
            task_id="T1",
            expected_failure_signature="ImportError",
            actual_output="importerror: cannot import name add",
            failure_category="import_error",
        )
    )

    assert ok is True
    assert reason is None


@pytest.mark.parametrize("category", ["syntax_error", "collection_error", "other"])
def test_verify_red_blocks_unacceptable_categories(category):
    ok, reason = verify_red(
        RedResult(
            task_id="T1",
            expected_failure_signature="SyntaxError",
            actual_output="SyntaxError: invalid syntax",
            failure_category=category,
        )
    )

    assert ok is False
    assert category in reason
