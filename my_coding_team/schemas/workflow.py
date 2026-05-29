"""Workflow routing and shared team-state schemas."""

from __future__ import annotations

from typing import Any, Literal

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
    suggested_review_input: dict[str, Any] | None = None


class ReviewOnlyInput(StrictBaseModel):
    """Review-only workflow input shape."""

    input_kind: Literal["file_list", "workspace_diff", "pasted_text"]
    files_to_review: list[str] = Field(default_factory=list)
    diff_base: str | None = None
    diff_target: str | None = None
    pasted_content: str | None = None
    pasted_language_hint: str | None = None
    user_focus_hint: str | None = None

    @model_validator(mode="after")
    def validate_input_consistency(self) -> "ReviewOnlyInput":
        """Ensure the selected review input mode has its required fields."""
        if self.input_kind == "file_list" and not self.files_to_review:
            raise ValueError("file_list mode requires files_to_review")
        if self.input_kind == "pasted_text" and not self.pasted_content:
            raise ValueError("pasted_text mode requires pasted_content")
        return self


class ProblemFrame(StrictBaseModel):
    """Phase 9a Shape 输出的问题框架。"""

    user_request: str
    problem: str
    goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    candidate_directions: list[str] = Field(default_factory=list)
    recommended_direction: str = ""
    confidence: Confidence = 1.0
    evidence: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_directions(self) -> "ProblemFrame":
        """确保 candidate_directions 数量合法且 recommended 在其中。"""
        if not self.candidate_directions:
            return self
        if self.recommended_direction and self.recommended_direction not in self.candidate_directions:
            raise ValueError("recommended_direction must be one of candidate_directions")
        if not (2 <= len(self.candidate_directions) <= 4):
            raise ValueError(f"candidate_directions must have 2-4 items, got {len(self.candidate_directions)}")
        return self


class ProductBrief(StrictBaseModel):
    """Phase 9a Specification 输出的产品简报。"""

    title: str
    summary: str
    goals: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    confidence: Confidence = 1.0
    evidence: list[Evidence] = Field(default_factory=list)


class DesignSignoff(StrictBaseModel):
    """设计确认结果，Full Flow 后续阶段使用。"""

    permission_to_plan: bool
    approved_by: str | None = None
    reason: str = ""
    notes: str = ""
    approved_direction: str = ""
    approved_scope: list[str] = Field(default_factory=list)
    accepted_assumptions: list[str] = Field(default_factory=list)
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
    review_only_input: dict[str, Any] | None = None
    problem_frame: ProblemFrame | None = None
    product_brief: ProductBrief | None = None
    design_signoff: DesignSignoff | None = None
    workspace: WorkspaceRecord | None = None
    repo_context: RepoContext | None = None
    task_queue: list[dict[str, Any]] = Field(default_factory=list)
    task_results: list[dict[str, Any]] = Field(default_factory=list)
    final_verification_plan: dict[str, Any] | None = None
    final_verification: dict[str, Any] | None = None
    final_review: dict[str, Any] | None = None
    red_results: list[dict[str, Any]] = Field(default_factory=list)
    pm_overrides: list[dict[str, Any]] = Field(default_factory=list)
    blocked_reason: str | None = None
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
