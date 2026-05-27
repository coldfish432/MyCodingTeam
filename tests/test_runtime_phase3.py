import pytest

from my_coding_team.runtime.factory import create_agent
from my_coding_team.runtime.middleware import CostBudget, parse_schema
from my_coding_team.runtime.mock_model import DeterministicModel
from my_coding_team.runtime.prompts import PromptNotFoundError, load_prompt
from my_coding_team.schemas.workflow import RouteDecision


def test_prompt_loader_fails_clearly_for_missing_prompt():
    with pytest.raises(PromptNotFoundError):
        load_prompt("does_not_exist")


@pytest.mark.asyncio
async def test_mock_model_output_parses_to_schema():
    model = DeterministicModel(
        json_outputs=[
            {
                "workflow": "direct_answer",
                "risk": "low",
                "confidence": 0.9,
                "rationale": "test",
            }
        ]
    )

    parsed = parse_schema(RouteDecision, await model.complete_json("route"))

    assert parsed.workflow == "direct_answer"


def test_cost_budget_blocks_when_exceeded():
    budget = CostBudget(limit=1)
    budget.charge()

    with pytest.raises(RuntimeError, match="blocked_by_budget_exceeded"):
        budget.charge()


def test_factory_can_create_agent_with_mock_model():
    agent = create_agent(
        name="TestAgent",
        system_prompt="test",
        model=DeterministicModel(),
        tools=[],
    )

    assert agent.name == "TestAgent"
