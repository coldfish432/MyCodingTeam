"""Phase 9a Shape Agent — mock model 测试。"""

import pytest

from my_coding_team.agents.shape import _fallback_shape
from my_coding_team.core.registry import STEPS
from my_coding_team.core.step import StepContext
from my_coding_team.schemas.step_inputs import ShapeInput
from my_coding_team.schemas.workflow import ProblemFrame


@pytest.mark.asyncio
async def test_shape_fallback_returns_problem_frame():
    """没有模型时 fallback 应返回最小 ProblemFrame。"""
    frame = await STEPS["shape"].run(ShapeInput(request="Add user authentication"), StepContext(model=None))
    assert isinstance(frame, ProblemFrame)
    assert frame.user_request == "Add user authentication"
    assert len(frame.candidate_directions) >= 1


@pytest.mark.asyncio
async def test_shape_with_mock_model_parse():
    """mock 模型应该能 parse 出合法 ProblemFrame。"""
    from my_coding_team.runtime.mock_model import DeterministicModel

    model = DeterministicModel(json_outputs=[{
        "user_request": "Add login page",
        "problem": "The app needs a login page for user authentication.",
        "goals": ["Create login UI", "Handle auth tokens"],
        "constraints": ["Must use React", "Must support dark mode"],
        "risks": ["XSS vulnerability in login form"],
        "candidate_directions": [
            "Server-side rendered login with session cookies",
            "SPA login with JWT and refresh tokens",
            "OAuth-only with Google/GitHub providers"
        ],
        "recommended_direction": "SPA login with JWT and refresh tokens",
        "confidence": 0.85,
        "evidence": [{"path": ".", "note": "based on existing SPA architecture"}]
    }])

    frame = await STEPS["shape"].run(ShapeInput(request="Add login page"), StepContext(model=model))
    assert frame.recommended_direction in frame.candidate_directions
    assert 2 <= len(frame.candidate_directions) <= 4
    assert frame.confidence == 0.85


@pytest.mark.asyncio
async def test_shape_fallback_structure():
    """fallback 应包含单候选方向且 recommended 在其中。"""
    frame = _fallback_shape("Fix typo")
    assert len(frame.candidate_directions) == 2
    assert frame.recommended_direction in frame.candidate_directions
    assert frame.confidence == 0.5
