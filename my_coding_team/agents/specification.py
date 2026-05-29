"""Phase 9a specification step: refine ProblemFrame into ProductBrief."""

from __future__ import annotations

from my_coding_team.core.registry import register_step
from my_coding_team.core.step import LLMBackedStep, StepContext
from my_coding_team.runtime.middleware import dumps_for_prompt, parse_schema
from my_coding_team.runtime.prompts import load_prompt
from my_coding_team.schemas.step_inputs import SpecificationInput
from my_coding_team.schemas.workflow import ProblemFrame, ProductBrief


class SpecificationStep(LLMBackedStep[SpecificationInput, ProductBrief]):
    name = "specification"
    input_schema = SpecificationInput
    output_schema = ProductBrief

    def build_prompt_input(self, input: SpecificationInput) -> str:
        problem_frame = ProblemFrame.model_validate(input.problem_frame)
        prompt = load_prompt("specification")
        context = f"ProblemFrame:\n{dumps_for_prompt(problem_frame)}\n"
        return f"{prompt}\n\n{context}"

    def make_agent(self, context: StepContext):
        return context.model

    async def run(self, input: SpecificationInput, context: StepContext) -> ProductBrief:
        problem_frame = ProblemFrame.model_validate(input.problem_frame)
        if context.model is None:
            return _fallback_spec(problem_frame)
        payload = await context.model.complete_json(self.build_prompt_input(input))
        context.llm_call_charge += 1
        return parse_schema(ProductBrief, payload)


SPECIFICATION = register_step(SpecificationStep())


def _fallback_spec(problem_frame: ProblemFrame) -> ProductBrief:
    """Generate a conservative ProductBrief without a model."""
    return ProductBrief(
        title=problem_frame.problem[:80],
        summary=f"Implement: {problem_frame.problem}",
        goals=list(problem_frame.goals),
        non_goals=["performance optimization", "backward compatibility beyond current API"],
        requirements=list(problem_frame.goals),
        acceptance_criteria=[f"Verify: {goal}" for goal in problem_frame.goals],
        risks=list(problem_frame.risks),
        assumptions=["implementation follows existing project conventions"],
        open_questions=[],
        confidence=0.5,
    )
