"""Phase 9a shape step: narrow fuzzy requests into ProblemFrame."""

from __future__ import annotations

import json

from my_coding_team.core.registry import register_step
from my_coding_team.core.step import LLMBackedStep, StepContext
from my_coding_team.runtime.middleware import dumps_for_prompt, parse_schema
from my_coding_team.runtime.prompts import load_prompt
from my_coding_team.schemas.step_inputs import ShapeInput
from my_coding_team.schemas.workflow import ProblemFrame


class ShapeStep(LLMBackedStep[ShapeInput, ProblemFrame]):
    name = "shape"
    input_schema = ShapeInput
    output_schema = ProblemFrame

    def build_prompt_input(self, input: ShapeInput) -> str:
        prompt = load_prompt("shape")
        context = f"User request:\n{input.request}\n"
        if input.route:
            context += f"\nRoute decision:\n{dumps_for_prompt(input.route)}\n"
        return f"{prompt}\n\n{context}"

    def make_agent(self, context: StepContext):
        return context.model

    async def run(self, input: ShapeInput, context: StepContext) -> ProblemFrame:
        if context.model is None:
            return _fallback_shape(input.request)
        payload = await context.model.complete_json(self.build_prompt_input(input))
        context.llm_call_charge += 1
        try:
            return parse_schema(ProblemFrame, payload)
        except Exception:
            return _repair_or_fallback_shape(payload, input.request)


SHAPE = register_step(ShapeStep())


def _repair_or_fallback_shape(payload: str | dict, request: str) -> ProblemFrame:
    """Repair common model shape issues or fall back deterministically."""
    try:
        data = json.loads(payload) if isinstance(payload, str) else dict(payload)
    except Exception:
        return _fallback_shape(request)

    candidates: list[str] = data.get("candidate_directions", [])
    recommended: str = data.get("recommended_direction", "")

    if len(candidates) < 2:
        for direction in ["direct implementation", "incremental refinement"]:
            if direction not in candidates:
                candidates.append(direction)
            if len(candidates) >= 2:
                break
        data["candidate_directions"] = candidates

    if recommended and recommended not in candidates:
        data["recommended_direction"] = candidates[0]

    try:
        return parse_schema(ProblemFrame, data)
    except Exception:
        return _fallback_shape(request)


def _fallback_shape(request: str) -> ProblemFrame:
    """Generate a conservative ProblemFrame without a model."""
    return ProblemFrame(
        user_request=request,
        problem=request,
        goals=[request],
        constraints=[],
        risks=["no model available for deep shaping"],
        candidate_directions=["direct implementation", "incremental refinement"],
        recommended_direction="direct implementation",
        confidence=0.5,
    )
