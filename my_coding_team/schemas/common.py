"""Common schema primitives shared across the workflow."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
OutputStatus = Literal["success", "needs_clarification", "blocked", "failed"]
RiskLevel = Literal["low", "medium", "high"]
WorkflowKind = Literal["direct_answer", "review_only", "lightweight", "full"]


class StrictBaseModel(BaseModel):
    """Base schema policy for project-owned data contracts."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Evidence(StrictBaseModel):
    """证据引用，用于 review、context 和 delivery 中定位事实来源。

    字段：
        path: 证据所在文件或目录。
        line: 可选行号。
        quote: 可选原文摘录。
        note: 证据说明。
    """

    path: str
    line: int | None = Field(default=None, ge=1)
    quote: str | None = None
    note: str = ""


class AgentOutput(StrictBaseModel):
    """通用 Agent 输出外壳。

    字段：
        agent_name: 输出来源 Agent。
        status: 执行状态。
        summary: 摘要。
        confidence: 置信度，范围 0.0 到 1.0。
        evidence: 支撑输出的证据列表。
        warnings: 非阻断警告。
    """

    agent_name: str
    status: OutputStatus
    summary: str = ""
    confidence: Confidence = 1.0
    evidence: list[Evidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
