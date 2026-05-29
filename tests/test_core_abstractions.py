import pytest
from pydantic import BaseModel

from my_coding_team.core.registry import ROOMS, STEPS, register_room, register_step
from my_coding_team.core.room import Room
from my_coding_team.core.step import LLMBackedStep, PythonStep, Step, StepContext


class InModel(BaseModel):
    value: str


class OutModel(BaseModel):
    value: str


def test_step_subclass_must_implement_run():
    class MissingRun(Step[InModel, OutModel]):
        name = "missing"
        input_schema = InModel
        output_schema = OutModel

    with pytest.raises(TypeError):
        MissingRun()


@pytest.mark.asyncio
async def test_python_step_instance_can_run():
    class EchoStep(PythonStep[InModel, OutModel]):
        name = "echo"
        input_schema = InModel
        output_schema = OutModel

        async def run(self, input: InModel, context: StepContext) -> OutModel:
            return OutModel(value=input.value)

    result = await EchoStep().run(InModel(value="ok"), StepContext())

    assert result.value == "ok"


def test_llm_backed_step_requires_prompt_and_agent_methods():
    class MissingMethods(LLMBackedStep[InModel, OutModel]):
        name = "missing_llm"
        input_schema = InModel
        output_schema = OutModel

        async def run(self, input: InModel, context: StepContext) -> OutModel:
            return OutModel(value=input.value)

    with pytest.raises(TypeError):
        MissingMethods()


def test_room_subclass_must_implement_execute():
    class MissingExecute(Room[InModel, OutModel]):
        name = "missing_room"
        input_schema = InModel
        output_schema = OutModel

    with pytest.raises(TypeError):
        MissingExecute()


def test_registry_registers_and_overwrites():
    class EchoStep(PythonStep[InModel, OutModel]):
        name = "test_echo"
        input_schema = InModel
        output_schema = OutModel

        async def run(self, input: InModel, context: StepContext) -> OutModel:
            return OutModel(value=input.value)

    first = EchoStep()
    second = EchoStep()
    register_step(first)
    assert STEPS["test_echo"] is first
    register_step(second)
    assert STEPS["test_echo"] is second


def test_room_registry_registers():
    class EchoRoom(Room[InModel, OutModel]):
        name = "test_room"
        input_schema = InModel
        output_schema = OutModel

        async def execute(self, input: InModel, context: StepContext) -> OutModel:
            return OutModel(value=input.value)

    room = register_room(EchoRoom())

    assert ROOMS["test_room"] is room


def test_step_context_llm_call_charge_is_mutable():
    context = StepContext()
    context.llm_call_charge += 1

    assert context.llm_call_charge == 1


def test_phase_10_5_registry_contains_expected_nodes():
    import my_coding_team.agents.context_scout  # noqa: F401
    import my_coding_team.agents.intake_router  # noqa: F401
    import my_coding_team.agents.planning  # noqa: F401
    import my_coding_team.agents.qa_verification  # noqa: F401
    import my_coding_team.agents.shape  # noqa: F401
    import my_coding_team.agents.specification  # noqa: F401
    import my_coding_team.rooms.implementation_room  # noqa: F401
    import my_coding_team.rooms.review_room  # noqa: F401
    import my_coding_team.rooms.tdd_room  # noqa: F401

    assert {
        "intake_router",
        "context_scout",
        "planning_single",
        "planning_queue",
        "qa_verification",
        "shape",
        "specification",
    }.issubset(STEPS)
    assert {"review_room", "tdd_room", "implementation_room"}.issubset(ROOMS)
