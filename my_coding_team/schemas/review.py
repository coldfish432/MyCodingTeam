"""Review result schemas."""

from __future__ import annotations

from pydantic import Field, model_validator

from my_coding_team.schemas.common import Evidence, RiskLevel, StrictBaseModel


class ReviewFinding(StrictBaseModel):
    """单条审查发现。

    字段：
        finding_id: 发现 ID。
        title: 简短标题。
        severity: 风险级别。
        approval: 该发现是否允许通过。
        must_fix: 必修复项列表，非空时必须 approval=false。
        evidence: must_fix 的证据。
        file_path: 可选文件路径。
        line: 可选行号。
    """

    finding_id: str
    title: str
    severity: RiskLevel = "medium"
    approval: bool = True
    must_fix: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    file_path: str | None = None
    line: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_must_fix(self) -> "ReviewFinding":
        """校验 must_fix 与 approval/evidence 的一致性。"""
        if self.must_fix and self.approval:
            raise ValueError("ReviewFinding with must_fix must set approval=false")
        if self.must_fix and not self.evidence:
            raise ValueError("ReviewFinding with must_fix requires evidence")
        return self


class TaskReviewResult(StrictBaseModel):
    """单任务审查结果。"""

    task_id: str
    approval: bool
    summary: str = ""
    findings: list[ReviewFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_approval(self) -> "TaskReviewResult":
        """有未解决 must_fix 时禁止 approval=true。"""
        if any(finding.must_fix for finding in self.findings) and self.approval:
            raise ValueError("TaskReviewResult cannot approve unresolved must_fix findings")
        return self


class FinalReviewReport(StrictBaseModel):
    """最终审查报告，DeliveryPackage 使用该结构。"""

    approval: bool
    summary: str = ""
    findings: list[ReviewFinding] = Field(default_factory=list)
    residual_risks: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_approval(self) -> "FinalReviewReport":
        """有未解决 must_fix 时禁止最终审查通过。"""
        if any(finding.must_fix for finding in self.findings) and self.approval:
            raise ValueError("FinalReviewReport cannot approve unresolved must_fix findings")
        return self
