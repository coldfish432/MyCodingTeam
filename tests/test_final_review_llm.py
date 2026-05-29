"""9-Final-3: Final ReviewRoom LLM 测试。"""

import pytest

from my_coding_team.agents.review_room import (
    _review_final,
    _validate_must_fix_has_file_evidence,
    _review_final_deterministic,
)
from my_coding_team.schemas.review import FinalReviewReport, ReviewFinding
from my_coding_team.schemas.task import ImplementationResult, TaskRunResult, VerificationResult
from my_coding_team.schemas.workflow import ProductBrief


@pytest.mark.asyncio
async def test_final_review_deterministic_fallback_when_no_model():
    """model=None → 走 deterministic fallback，不抛错。"""
    result = await _review_final(
        brief=None,
        task_results=[],
        final_verification=None,
        model=None,
    )
    assert isinstance(result, FinalReviewReport)


@pytest.mark.asyncio
async def test_final_review_llm_mock_must_fix_with_evidence():
    """LLM 返回带 must_fix + 文件 evidence → 正常 parse。"""
    from my_coding_team.runtime.mock_model import DeterministicModel

    brief = ProductBrief(
        title="Test",
        summary="Test.",
        goals=["G1"],
        non_goals=["N1", "N2"],
        acceptance_criteria=["pytest passes"],
    )
    tr = TaskRunResult(
        task_id="T1",
        status="completed",
        implementation=ImplementationResult(task_id="T1", success=True, summary="done", changed_files=["src/a.py"]),
        verification=VerificationResult(task_id="T1", passed=True, commands=["pytest"]),
    )
    final_ver = VerificationResult(task_id="final", passed=True, commands=["pytest"])

    model = DeterministicModel(json_outputs=[{
        "findings": [
            {
                "finding_id": "f1",
                "title": "Cross-task signature mismatch",
                "severity": "high",
                "approval": False,
                "must_fix": ["Fix inconsistent log() signatures between task T1 and T2"],
                "evidence": [{"path": "src/a.py", "note": "log(event, payload)"}, {"path": "src/b.py", "note": "log(payload, event)"}],
                "file_path": "src/a.py",
            },
        ],
        "approval": False,
        "summary": "Found cross-task inconsistency",
        "residual_risks": ["Potential race condition in event handler"],
    }])

    result = await _review_final(
        brief=brief,
        task_results=[tr],
        final_verification=final_ver,
        model=model,
    )
    assert isinstance(result, FinalReviewReport)
    assert result.approval is False
    assert len(result.findings) >= 1
    assert "residual_risks" in result.model_fields


@pytest.mark.asyncio
async def test_final_review_llm_mock_all_clear():
    """LLM 返回空 findings → approval=True。"""
    from my_coding_team.runtime.mock_model import DeterministicModel

    brief = ProductBrief(
        title="Test",
        summary="Test.",
        goals=["G1"],
        non_goals=["N1", "N2"],
        acceptance_criteria=["pytest"],
    )
    tr = TaskRunResult(
        task_id="T1",
        status="completed",
        implementation=ImplementationResult(task_id="T1", success=True, summary="done"),
        verification=VerificationResult(task_id="T1", passed=True, commands=["pytest"]),
    )
    final_ver = VerificationResult(task_id="final", passed=True, commands=["pytest"])

    model = DeterministicModel(json_outputs=[{
        "findings": [],
        "approval": True,
        "summary": "All good",
        "residual_risks": [],
    }])

    result = await _review_final(
        brief=brief,
        task_results=[tr],
        final_verification=final_ver,
        model=model,
    )
    assert result.approval is True


@pytest.mark.asyncio
async def test_final_review_llm_failure_falls_back():
    """LLM 返回无法 parse 的数据 → fallback deterministic。"""
    from my_coding_team.runtime.mock_model import DeterministicModel

    model = DeterministicModel(json_outputs=[{"garbage": True}])

    result = await _review_final(
        brief=None,
        task_results=[],
        final_verification=None,
        model=model,
    )
    assert isinstance(result, FinalReviewReport)


def test_validate_must_fix_has_file_evidence_passes():
    """有文件路径的 evidence → 不抛错。"""
    finding = ReviewFinding(
        finding_id="f1",
        title="Bug",
        severity="high",
        approval=False,
        must_fix=["fix it"],
        evidence=[{"path": "src/a.py", "note": "broken"}],
    )
    _validate_must_fix_has_file_evidence(finding)


def test_validate_must_fix_no_evidence_rejects():
    """must_fix 没有文件 evidence → ValueError。"""
    finding = ReviewFinding(
        finding_id="f1",
        title="Vague",
        severity="high",
        approval=False,
        must_fix=["code should be better"],
        evidence=[{"path": ".", "note": "it feels off"}],
    )
    with pytest.raises(ValueError, match="file-level evidence"):
        _validate_must_fix_has_file_evidence(finding)


def test_validate_must_fix_empty_skips():
    """没有 must_fix → 不校验。"""
    finding = ReviewFinding(
        finding_id="f1",
        title="note",
        severity="low",
        approval=True,
        must_fix=[],
        evidence=[],
    )
    _validate_must_fix_has_file_evidence(finding)
