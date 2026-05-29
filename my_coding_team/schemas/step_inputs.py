"""Input schemas for Step.run()."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from my_coding_team.schemas.common import StrictBaseModel
from my_coding_team.schemas.workflow import WorkspaceRecord


class IntakeRouterInput(StrictBaseModel):
    request: str


class ContextScoutInput(StrictBaseModel):
    request: str
    workspace: WorkspaceRecord


class PlanningSingleInput(StrictBaseModel):
    request: str
    repo_context: dict[str, Any]
    workspace: WorkspaceRecord


class PlanningQueueInput(StrictBaseModel):
    brief: dict[str, Any]
    repo_context: dict[str, Any]


class QAVerificationInput(StrictBaseModel):
    contract: dict[str, Any] | None = None
    workspace_root: str | None = None
    scope: Literal["task", "final"] = "task"
    commands: list[str] | None = None
    timeout_seconds: int = Field(default=60, ge=1)


class ShapeInput(StrictBaseModel):
    request: str
    route: dict[str, Any] | None = None


class SpecificationInput(StrictBaseModel):
    problem_frame: dict[str, Any]
