"""ImplementationRoom wrapper."""

from __future__ import annotations

from my_coding_team.agents.task_implementation import run_task_implementation
from my_coding_team.core.registry import register_room
from my_coding_team.core.room import Room
from my_coding_team.core.step import StepContext
from my_coding_team.schemas.room_inputs import ImplementationRoomInput
from my_coding_team.schemas.task import ImplementationResult, TaskContract, TaskRepairContract


class ImplementationRoom(Room[ImplementationRoomInput, ImplementationResult]):
    """Implementation room. Phase 10.5 keeps the existing single Coder path."""

    name = "implementation_room"
    input_schema = ImplementationRoomInput
    output_schema = ImplementationResult

    async def execute(self, input: ImplementationRoomInput, context: StepContext) -> ImplementationResult:
        contract_data = input.contract
        if "original_task_id" in contract_data:
            contract = TaskRepairContract.model_validate(contract_data)
        else:
            contract = TaskContract.model_validate(contract_data)
        return await run_task_implementation(contract, input.workspace_root, model=context.model)


IMPLEMENTATION_ROOM = register_room(ImplementationRoom())
