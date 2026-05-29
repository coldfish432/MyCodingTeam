"""Phase 9a Specification Agent — mock model 测试。"""

import pytest

from my_coding_team.agents.specification import _fallback_spec
from my_coding_team.core.registry import STEPS
from my_coding_team.core.step import StepContext
from my_coding_team.schemas.step_inputs import SpecificationInput
from my_coding_team.schemas.workflow import ProblemFrame, ProductBrief


@pytest.mark.asyncio
async def test_specification_fallback_returns_product_brief():
    """没有模型时 fallback 应返回最小 ProductBrief。"""
    frame = ProblemFrame(
        user_request="Add auth",
        problem="Need authentication",
        goals=["Implement login"],
        candidate_directions=["JWT auth", "Session auth"],
        recommended_direction="JWT auth",
    )
    brief = await STEPS["specification"].run(
        SpecificationInput(problem_frame=frame.model_dump()),
        StepContext(model=None),
    )
    assert isinstance(brief, ProductBrief)
    assert brief.title
    assert len(brief.goals) > 0
    assert len(brief.non_goals) > 0


@pytest.mark.asyncio
async def test_specification_with_mock_model_parse():
    """mock 模型应该能 parse 出合法 ProductBrief。"""
    from my_coding_team.runtime.mock_model import DeterministicModel

    frame = ProblemFrame(
        user_request="Add dark mode",
        problem="App needs dark mode support",
        goals=["Add theme toggle", "Style components for dark mode"],
        candidate_directions=["CSS variables approach", "CSS-in-JS theme provider"],
        recommended_direction="CSS variables approach",
    )

    model = DeterministicModel(json_outputs=[{
        "title": "Dark Mode Support",
        "summary": "Add dark mode toggle with CSS variable-based theming.",
        "goals": ["Add theme toggle", "Style components for dark mode"],
        "non_goals": ["High-contrast mode", "Custom color schemes", "Per-component theme overrides"],
        "requirements": ["Toggle switches theme globally", "Preference persisted in localStorage"],
        "acceptance_criteria": ["Toggle button visible on all pages", "Dark mode covers all existing components"],
        "risks": ["Some third-party components may not respect CSS variables"],
        "assumptions": ["Browser supports CSS custom properties"],
        "open_questions": [],
        "confidence": 0.9,
        "evidence": [{"path": ".", "note": "derived from ProblemFrame"}]
    }])

    brief = await STEPS["specification"].run(
        SpecificationInput(problem_frame=frame.model_dump()),
        StepContext(model=model),
    )
    assert brief.title == "Dark Mode Support"
    assert len(brief.non_goals) == 3
    assert len(brief.requirements) == 2
    assert brief.confidence == 0.9


@pytest.mark.asyncio
async def test_specification_fallback_has_required_fields():
    """fallback ProductBrief 必须有 non_goals 和 assumptions。"""
    frame = ProblemFrame(
        user_request="x", problem="x",
        goals=["Implement X feature"],
        candidate_directions=["a", "b"],
        recommended_direction="a",
    )
    brief = _fallback_spec(frame)
    assert brief.non_goals
    assert brief.assumptions
    assert brief.acceptance_criteria
