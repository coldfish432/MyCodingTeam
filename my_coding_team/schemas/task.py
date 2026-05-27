"""Task planning, implementation, and verification schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from my_coding_team.schemas.common import Evidence, RiskLevel, StrictBaseModel


TaskStatus = Literal["pending", "running", "blocked", "passed", "failed"]


class TaskItem(StrictBaseModel):
    """任务队列中的轻量任务条目。"""

    task_id: str
    title: str
    description: str = ""
    allowed_files: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    risk: RiskLevel = "low"
    status: TaskStatus = "pending"


class TaskQueue(StrictBaseModel):
    """任务队列；MVP 只使用单任务，Phase 9b 扩展多任务。"""

    items: list[TaskItem] = Field(default_factory=list)
    strategy: str = "sequential"

    @model_validator(mode="after")
    def validate_unique_task_ids(self) -> "TaskQueue":
        """确保队列中 task_id 唯一。"""
        task_ids = [item.task_id for item in self.items]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("TaskQueue task_id values must be unique")
        return self


class TaskContract(StrictBaseModel):
    """实现 Agent 和 QA 共同遵守的任务合同。

    字段：
        task_id: 任务 ID。
        objective: 任务目标。
        allowed_files: 唯一允许写入/编辑的文件范围。
        verification_commands: QA 允许运行的验证命令。
        prohibited_files: 明确禁止触碰的文件。
        risk: 风险级别。
        evidence: 合同来源证据。
    """

    task_id: str
    objective: str
    allowed_files: list[str]
    verification_commands: list[str] = Field(default_factory=list)
    prohibited_files: list[str] = Field(default_factory=list)
    risk: RiskLevel = "low"
    evidence: list[Evidence] = Field(default_factory=list)

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
    evidence: list[Evidence] = Field(default_factory=list)

    @field_validator("allowed_files")
    @classmethod
    def allowed_files_must_not_be_empty(cls, value: list[str]) -> list[str]:
        """repair 合同也必须保留 allowed_files 边界。"""
        if not value:
            raise ValueError("allowed_files must not be empty")
        return value


class RedResult(StrictBaseModel):
    """Phase 8 TDD RED 结果占位 schema，MVP 不执行 RED。"""

    task_id: str
    red_required: bool = False
    passed: bool = False
    expected_failure_signature: str | None = None
    observed_failure: str | None = None
    skipped_reason: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)


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


class TaskRunResult(StrictBaseModel):
    """单任务完整运行结果。"""

    task_id: str
    implementation: ImplementationResult
    verification: VerificationResult
    review: object
    repair_attempts: int = Field(default=0, ge=0)
    blocked: bool = False
    blocked_reason: str | None = None
