"""Delivery decision schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from my_coding_team.schemas.common import Confidence, Evidence, StrictBaseModel
from my_coding_team.schemas.review import FinalReviewReport
from my_coding_team.schemas.task import VerificationResult


FinishStatus = Literal["success", "blocked", "failed"]


class FinishDecision(StrictBaseModel):
    """交付裁决。

    字段：
        status: success、blocked 或 failed。
        reason: 裁决原因。
        confidence: 裁决置信度。
        evidence: 支撑裁决的证据。
    """

    status: FinishStatus
    reason: str
    confidence: Confidence = 1.0
    evidence: list[Evidence] = Field(default_factory=list)


class DeliveryPackage(StrictBaseModel):
    """面向用户和 CLI 的最终交付包。

    字段：
        request: 原始请求。
        decision: 交付裁决。
        summary: 结果摘要。
        changed_files: 修改文件列表。
        verification: 验证结果列表。
        review: 最终审查报告。
        risks: 剩余风险。
        llm_calls_used: 本次流程消耗的 LLM 调用数。
    """

    request: str
    decision: FinishDecision
    summary: str = ""
    changed_files: list[str] = Field(default_factory=list)
    verification: list[VerificationResult] = Field(default_factory=list)
    review: FinalReviewReport | None = None
    risks: list[str] = Field(default_factory=list)
    llm_calls_used: int = Field(default=0, ge=0)
    workflow_kind: Literal["direct_answer", "review_only", "lightweight", "full"] | None = None
    red_results: list[dict] = Field(default_factory=list)
    pm_overrides: list[dict] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_review_only_no_writes(self) -> "DeliveryPackage":
        """Review-only delivery must never report file writes."""
        if self.workflow_kind == "review_only" and self.changed_files:
            raise ValueError("review_only workflow must produce empty changed_files")
        return self
