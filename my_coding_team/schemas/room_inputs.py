"""Input schemas for Room.execute()."""

from __future__ import annotations

from typing import Any, Literal

from my_coding_team.schemas.common import StrictBaseModel


class ReviewRoomInput(StrictBaseModel):
    scope: Literal["task", "final", "review_only"] = "task"
    contract: dict[str, Any] | None = None
    implementation: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    red: dict[str, Any] | None = None
    brief: dict[str, Any] | None = None
    task_results: list[dict[str, Any]] | None = None
    final_verification: dict[str, Any] | None = None
    review_only_input: dict[str, Any] | None = None
    review_target_blob: str | None = None
    repo_context: dict[str, Any] | None = None


class TDDRoomInput(StrictBaseModel):
    contract: dict[str, Any]
    workspace_root: str
    timeout_seconds: int = 60


class TDDRoomOutput(StrictBaseModel):
    red_result: dict[str, Any]
    verified: bool
    mismatch_reason: str | None = None


class ImplementationRoomInput(StrictBaseModel):
    contract: dict[str, Any]
    workspace_root: str
