"""ReviewRoom wrapper."""

from __future__ import annotations

from my_coding_team.agents.review_room import _review_final, _review_only, _review_task
from my_coding_team.core.registry import register_room
from my_coding_team.core.room import Room
from my_coding_team.core.step import StepContext
from my_coding_team.schemas.review import FinalReviewReport, ReviewOnlyReport, TaskReviewResult
from my_coding_team.schemas.room_inputs import ReviewRoomInput
from my_coding_team.schemas.task import ImplementationResult, RedResult, TaskContract, TaskRunResult, VerificationResult
from my_coding_team.schemas.workflow import ProductBrief, RepoContext, ReviewOnlyInput


class ReviewRoom(Room[ReviewRoomInput, TaskReviewResult | FinalReviewReport | ReviewOnlyReport]):
    """Review room. Phase 10.5 keeps the existing single-member behavior."""

    name = "review_room"
    input_schema = ReviewRoomInput
    output_schema = TaskReviewResult

    async def execute(
        self,
        input: ReviewRoomInput,
        context: StepContext,
    ) -> TaskReviewResult | FinalReviewReport | ReviewOnlyReport:
        if input.scope == "final":
            brief = ProductBrief.model_validate(input.brief) if input.brief else None
            task_results = [TaskRunResult.model_validate(item) for item in (input.task_results or [])]
            final_verification = (
                VerificationResult.model_validate(input.final_verification)
                if input.final_verification
                else None
            )
            return await _review_final(brief, task_results, final_verification, model=context.model)

        if input.scope == "review_only":
            if input.review_only_input is None or input.review_target_blob is None:
                raise ValueError("review_only scope requires review_only_input and review_target_blob")
            repo_context = RepoContext.model_validate(input.repo_context) if input.repo_context else None
            return await _review_only(
                input_spec=ReviewOnlyInput.model_validate(input.review_only_input),
                target_blob=input.review_target_blob,
                repo_context=repo_context,
                model=context.model,
            )

        return await _review_task(
            TaskContract.model_validate(input.contract) if input.contract else None,
            ImplementationResult.model_validate(input.implementation) if input.implementation else None,
            VerificationResult.model_validate(input.verification) if input.verification else None,
            red=RedResult.model_validate(input.red) if input.red else None,
            model=context.model,
        )


REVIEW_ROOM = register_room(ReviewRoom())
