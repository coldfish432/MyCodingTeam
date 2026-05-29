"""TDDRoom wrapper."""

from __future__ import annotations

from my_coding_team.agents.tdd import run_tdd_red
from my_coding_team.core.registry import register_room
from my_coding_team.core.room import Room
from my_coding_team.core.step import StepContext
from my_coding_team.schemas.room_inputs import TDDRoomInput, TDDRoomOutput
from my_coding_team.schemas.task import RedResult, TaskContract


class TDDRoom(Room[TDDRoomInput, TDDRoomOutput]):
    """TDD room. Phase 10.5 keeps one RedWriter plus deterministic verify_red."""

    name = "tdd_room"
    input_schema = TDDRoomInput
    output_schema = TDDRoomOutput

    async def execute(self, input: TDDRoomInput, context: StepContext) -> TDDRoomOutput:
        from my_coding_team.orchestration.task_runner import verify_red

        red = await run_tdd_red(
            TaskContract.model_validate(input.contract),
            input.workspace_root,
            context.model,
            timeout_seconds=input.timeout_seconds,
        )
        ok, reason = verify_red(red)
        return TDDRoomOutput(
            red_result=red.model_dump(),
            verified=ok,
            mismatch_reason=reason,
        )


TDD_ROOM = register_room(TDDRoom())
