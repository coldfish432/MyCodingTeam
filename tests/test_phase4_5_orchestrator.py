import pytest

from my_coding_team.agents.intake_router import route_request_deterministically
from my_coding_team.orchestration.pm_orchestrator import run_request
from my_coding_team.orchestration.state_machine import transition
from my_coding_team.runtime.mock_model import DeterministicModel


@pytest.mark.parametrize(
    ("user_request", "workflow"),
    [
        ("解释一下这个项目", "direct_answer"),
        ("review this PR", "review_only"),
        ("新增 README 内容", "lightweight"),
        ("设计完整系统架构", "full"),
    ],
)
def test_intake_router_routes_core_workflows(user_request, workflow):
    assert route_request_deterministically(user_request).workflow == workflow


@pytest.mark.asyncio
async def test_run_request_direct_answer_returns_delivery_package():
    package = await run_request(
        "解释一下 schema",
        mode="direct",
        model=DeterministicModel(text="schema explanation"),
    )

    assert package.decision.status == "success"
    assert package.summary == "schema explanation"
    assert package.changed_files == []


@pytest.mark.asyncio
async def test_run_request_blocks_on_budget_exceeded():
    package = await run_request(
        "解释一下 schema",
        budget=0,
        mode="direct",
        model=DeterministicModel(text="schema explanation"),
    )

    assert package.decision.status == "blocked"
    assert package.decision.reason == "blocked_by_budget_exceeded"


def test_illegal_state_transition_fails():
    with pytest.raises(ValueError):
        transition("initialized", "verified")
