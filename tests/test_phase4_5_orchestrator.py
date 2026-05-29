import pytest

from my_coding_team.agents.intake_router import route_request_deterministically
from my_coding_team.core.registry import STEPS
from my_coding_team.core.step import StepContext
from my_coding_team.orchestration.pm_orchestrator import run_request
from my_coding_team.orchestration.state_machine import transition
from my_coding_team.runtime.mock_model import DeterministicModel
from my_coding_team.schemas.step_inputs import IntakeRouterInput


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


@pytest.mark.parametrize(
    ("user_request", "workflow"),
    [
        ("帮我看看这个 PR", "review_only"),
        ("review my changes in src/auth.py", "review_only"),
        ("please inspect the diff and tell me risks", "review_only"),
        ("review my changes in src/auth.py and fix the issues", "lightweight"),
        ("检查 src/auth.py 并修复问题", "lightweight"),
        ("add a section to README", "lightweight"),
        ("review the auth module and implement a cross-module redesign", "full"),
    ],
)
def test_intake_router_review_edit_boundaries(user_request, workflow):
    assert route_request_deterministically(user_request).workflow == workflow


@pytest.mark.asyncio
async def test_intake_router_overrides_bad_model_route_for_review_boundary():
    route = await STEPS["intake_router"].run(
        IntakeRouterInput(request="review my changes in src/auth.py"),
        StepContext(
            model=DeterministicModel(
            json_outputs=[
                {
                    "workflow": "direct_answer",
                    "risk": "low",
                    "confidence": 0.9,
                    "rationale": "bad model route",
                },
            ],
            ),
        ),
    )

    assert route.workflow == "review_only"
    assert "boundary override" in route.rationale


@pytest.mark.asyncio
async def test_intake_router_overrides_bad_model_route_for_mixed_review_and_fix():
    route = await STEPS["intake_router"].run(
        IntakeRouterInput(request="review my changes in src/auth.py and fix the issues"),
        StepContext(
            model=DeterministicModel(
            json_outputs=[
                {
                    "workflow": "review_only",
                    "risk": "medium",
                    "confidence": 0.9,
                    "rationale": "bad model route",
                },
            ],
            ),
        ),
    )

    assert route.workflow == "lightweight"
    assert "boundary override" in route.rationale


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
