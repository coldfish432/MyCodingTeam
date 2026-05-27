"""Workflow routing and shared team-state schemas."""

from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from my_coding_team.schemas.common import (
    Confidence,
    Evidence,
    OutputStatus,
    RiskLevel,
    StrictBaseModel,
    WorkflowKind,
)


class RouteDecision(StrictBaseModel):
    """Intake Router 输出的流程路由决策。"""

    workflow: WorkflowKind
    risk: RiskLevel = "low"
    confidence: Confidence
    needs_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)
    rationale: str = ""


class ProblemFrame(StrictBaseModel):
    """Phase 9a Shape 输出的问题框架，MVP 中仅保留 schema。"""

    user_request: str
    problem: str
    goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    confidence: Confidence = 1.0
    evidence: list[Evidence] = Field(default_factory=list)


class ProductBrief(StrictBaseModel):
    """Phase 9a Specification 输出的产品简报，MVP 中仅保留 schema。"""

    title: str
    summary: str
    goals: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    confidence: Confidence = 1.0
    evidence: list[Evidence] = Field(default_factory=list)


class DesignSignoff(StrictBaseModel):
    """设计确认结果，Full Flow 后续阶段使用。"""

    approved: bool
    approved_by: str | None = None
    notes: str = ""
    evidence: list[Evidence] = Field(default_factory=list)


class WorkspaceRecord(StrictBaseModel):
    """工作区状态快照。"""

    root: str
    is_git: bool
    current_commit: str | None = None
    status_short: str = ""
    dirty_files: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class RepoContext(StrictBaseModel):
    """Context Scout 输出的仓库事实摘要。"""

    relevant_files: list[str] = Field(default_factory=list)
    test_entrypoints: list[str] = Field(default_factory=list)
    build_commands: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class TeamState(StrictBaseModel):
    """PM Orchestrator 在流程中推进的共享状态。"""

    request: str
    status: OutputStatus = "success"
    current_phase: str = "initialized"
    workflow: WorkflowKind | None = None
    route_decision: RouteDecision | None = None
    problem_frame: ProblemFrame | None = None
    product_brief: ProductBrief | None = None
    design_signoff: DesignSignoff | None = None
    workspace: WorkspaceRecord | None = None
    repo_context: RepoContext | None = None
    llm_calls_used: int = Field(default=0, ge=0)
    llm_calls_budget: int = Field(default=0, ge=0)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_budget(self) -> "TeamState":
        """确保已用 LLM 调用数不超过预算。"""
        if self.llm_calls_used > self.llm_calls_budget:
            raise ValueError("llm_calls_used must be <= llm_calls_budget")
        return self
