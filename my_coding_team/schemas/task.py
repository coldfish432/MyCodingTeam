"""Task planning, implementation, and verification schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from my_coding_team.schemas.common import Evidence, RiskLevel, StrictBaseModel


TaskStatus = Literal["pending", "running", "blocked", "passed", "failed"]


class TaskItem(StrictBaseModel):
    """任务队列中的轻量任务条目。"""

    task_id: str
    title: str
    description: str = ""
    files: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    risk: RiskLevel = "low"
    status: TaskStatus = "pending"


class TaskQueue(StrictBaseModel):
    """任务队列；支持单任务和多任务。"""

    items: list[TaskItem] = Field(default_factory=list)
    strategy: str = "sequential"
    estimated_total_calls: int = 0

    @model_validator(mode="after")
    def validate_queue(self) -> "TaskQueue":
        """确保队列大小合理且 task_id 唯一。"""
        if not (1 <= len(self.items) <= 15):
            raise ValueError(f"TaskQueue must have 1-15 items, got {len(self.items)}")
        task_ids = [item.task_id for item in self.items]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("TaskQueue task_id values must be unique")
        for item in self.items:
            if not (1 <= len(item.files) <= 8):
                raise ValueError(f"Task {item.task_id}: files must have 1-8 items, got {len(item.files)}")
        return self


class TaskContract(StrictBaseModel):
    """实现 Agent 和 QA 共同遵守的任务合同。

    字段：
        task_id: 任务 ID。
        goal: 任务目标。
        allowed_files: 唯一允许写入/编辑的文件范围。
        verification_commands: QA 允许运行的验证命令。
        prohibited_files: 明确禁止触碰的文件。
        risk: 风险级别。
        evidence: 合同来源证据。
        prior_task_summaries: 同一队列中前面已完成任务的摘要。
    """

    task_id: str
    goal: str
    allowed_files: list[str]
    verification_commands: list[str] = Field(default_factory=list)
    prohibited_files: list[str] = Field(default_factory=list)
    risk: RiskLevel = "low"
    evidence: list[Evidence] = Field(default_factory=list)
    test_first_requirement: Literal["required", "optional", "not_applicable"] | None = None
    red_allowed_files: list[str] = Field(default_factory=lambda: ["tests/**"])
    red_verification_command: str | None = None
    expected_failure_signature_hints: list[str] = Field(default_factory=list)
    prior_task_summaries: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("allowed_files")
    @classmethod
    def allowed_files_must_not_be_empty(cls, value: list[str]) -> list[str]:
        """禁止生成无写入边界的任务合同。"""
        if not value:
            raise ValueError("allowed_files must not be empty")
        return value


class TaskRepairContract(StrictBaseModel):
    """repair loop 使用的修复合同。"""

    original_task_id: str
    reason: str
    allowed_files: list[str]
    verification_commands: list[str] = Field(default_factory=list)
    red_allowed_files: list[str] = Field(default_factory=list)
    extend_allowed_files_to_red: bool = False
    evidence: list[Evidence] = Field(default_factory=list)

    @field_validator("allowed_files")
    @classmethod
    def allowed_files_must_not_be_empty(cls, value: list[str]) -> list[str]:
        """repair 合同也必须保留 allowed_files 边界。"""
        if not value:
            raise ValueError("allowed_files must not be empty")
        return value


class RedResult(StrictBaseModel):
    """Phase 8 TDD RED 结果。"""

    task_id: str
    red_type: Literal["test", "skip"] = "test"
    files_changed: list[str] = Field(default_factory=list)
    command: str = ""
    expected_failure_signature: str | None = None
    actual_output: str | None = None
    failed_for_expected_reason: bool = False
    failure_category: Literal[
        "assertion",
        "not_implemented",
        "import_error",
        "syntax_error",
        "collection_error",
        "other",
    ] | None = None
    failure_excerpt: str | None = None
    skip_reason: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def category_required_for_test(self) -> "RedResult":
        if self.red_type == "test" and self.failure_category is None:
            raise ValueError("failure_category is required when red_type='test'")
        return self


class ImplementationResult(StrictBaseModel):
    """实现阶段输出。"""

    task_id: str
    success: bool
    summary: str = ""
    changed_files: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class VerificationResult(StrictBaseModel):
    """验证阶段输出。"""

    task_id: str
    passed: bool
    commands: list[str] = Field(default_factory=list)
    failed_commands: list[str] = Field(default_factory=list)
    output_summary: str = ""
    evidence: list[Evidence] = Field(default_factory=list)


class AcceptanceCheck(StrictBaseModel):
    """Phase 9c Final Verification 的单条验收检查项。"""

    criterion: str
    verification_commands: list[str] = Field(default_factory=list)
    expected_outcome: str = ""
    not_run_fallback_reason: str | None = None


class FinalVerificationPlan(StrictBaseModel):
    """Phase 9c Final Verification Plan。"""

    acceptance_checks: list[AcceptanceCheck] = Field(default_factory=list)
    estimated_total_calls: int = 0


class TaskRunResult(StrictBaseModel):
    """单任务完整运行结果。"""

    task_id: str
    status: Literal[
        "completed",
        "blocked_must_fix",
        "blocked_budget",
        "blocked_schema",
        "blocked_red_mismatch",
        "blocked_permission_denied",
        "blocked_repair_limit",
    ] = "completed"
    implementation: ImplementationResult | None = None
    verification: VerificationResult | None = None
    review: Any | None = None
    repair_attempts: int = Field(default=0, ge=0)
    skip_reason: str | None = None
