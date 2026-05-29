"""Intake routing agent facade."""

from __future__ import annotations

import re

from my_coding_team.runtime.middleware import parse_schema
from my_coding_team.runtime.prompts import load_prompt
from my_coding_team.core.registry import register_step
from my_coding_team.core.step import LLMBackedStep, StepContext
from my_coding_team.schemas.step_inputs import IntakeRouterInput
from my_coding_team.schemas.workflow import RouteDecision


REVIEW_TERMS = (
    "review",
    "inspect",
    "check",
    "look at",
    "take a look",
    "diff",
    "changes",
    "看看",
    "检查",
    "审查",
    "评审",
)
PASTED_CODE_MARKERS = (
    "```",
    "def ",
    "class ",
    "function ",
    "const ",
    "let ",
    "var ",
)
CHANGE_TERMS = (
    "改",
    "修",
    "修复",
    "增加",
    "新增",
    "更新",
    "删除",
    "实现",
    "重构",
)
ENGLISH_CHANGE_TERMS = (
    "write",
    "fix",
    "add",
    "update",
    "change",
    "modify",
    "delete",
    "implement",
    "edit",
    "refactor",
)
BROAD_TERMS = (
    "architecture",
    "system",
    "cross-module",
    "full",
    "rewrite",
    "架构",
    "系统",
    "完整流程",
    "跨模块",
    "重写",
)


def route_request_deterministically(request: str) -> RouteDecision:
    """Route a request using deterministic boundary rules.

    The review/edit boundary is deliberately explicit:
    review-only requests may inspect code, PRs, or diffs, but must not ask for
    implementation. Requests that include both review wording and edit/fix/write
    wording route to implementation workflows.
    """
    text = request.lower().strip()
    if not text:
        return RouteDecision(
            workflow="direct_answer",
            risk="low",
            confidence=0.4,
            needs_clarification=True,
            clarification_questions=["What should the team do?"],
            rationale="empty request",
        )

    review_intent = _has_review_intent(text)
    change_intent = _has_change_intent(text)
    broad_intent = _has_broad_intent(text)

    if change_intent:
        if broad_intent:
            return RouteDecision(
                workflow="full",
                risk="high",
                confidence=0.85,
                rationale="broad change request",
            )
        return RouteDecision(
            workflow="lightweight",
            risk="medium",
            confidence=0.85,
            rationale="change request takes precedence over review wording",
        )
    if review_intent:
        return RouteDecision(
            workflow="review_only",
            risk="medium",
            confidence=0.85,
            rationale="review-only request without change intent",
            suggested_review_input=_suggest_review_input(request),
        )
    if broad_intent:
        return RouteDecision(workflow="full", risk="high", confidence=0.75, rationale="broad system request")
    return RouteDecision(workflow="direct_answer", risk="low", confidence=0.7, rationale="answer-only request")


def _has_review_intent(text: str) -> bool:
    return any(term in text for term in REVIEW_TERMS) or bool(re.search(r"\b(pr|pull request)\b", text))


def _has_change_intent(text: str) -> bool:
    return any(term in text for term in CHANGE_TERMS) or any(
        re.search(rf"\b{re.escape(term)}\b", text)
        for term in ENGLISH_CHANGE_TERMS
    )


def _has_broad_intent(text: str) -> bool:
    return any(term in text for term in BROAD_TERMS)


def make_intake_router_agent(model):
    """Build the IntakeRouter Agent with read-only search tools."""
    from my_coding_team.runtime.agentscope_adapter import Glob, Grep, PermissionMode, Read
    from my_coding_team.runtime.factory import create_agent

    return create_agent(
        name="IntakeRouter",
        system_prompt=load_prompt("intake_router"),
        model=model,
        tools=[Read(), Grep(), Glob()],
        permission_mode=PermissionMode.EXPLORE,
    )

class IntakeRouterStep(LLMBackedStep[IntakeRouterInput, RouteDecision]):
    name = "intake_router"
    input_schema = IntakeRouterInput
    output_schema = RouteDecision

    def build_prompt_input(self, input: IntakeRouterInput) -> str:
        return f"{load_prompt('intake_router')}\n\nRequest:\n{input.request}"

    def make_agent(self, context: StepContext):
        return context.model

    async def run(self, input: IntakeRouterInput, context: StepContext) -> RouteDecision:
        if context.model is None:
            return route_request_deterministically(input.request)
        prompt = self.build_prompt_input(input)
        model = self.make_agent(context)
        payload = await model.complete_json(prompt)
        context.llm_call_charge += 1
        model_route = parse_schema(RouteDecision, payload)
        deterministic_route = route_request_deterministically(input.request)
        if (
            deterministic_route.workflow in {"review_only", "lightweight", "full"}
            and deterministic_route.confidence >= 0.85
            and model_route.workflow != deterministic_route.workflow
        ):
            return deterministic_route.model_copy(
                update={
                    "rationale": f"deterministic boundary override: {deterministic_route.rationale}",
                },
            )
        if model_route.workflow == "review_only" and model_route.suggested_review_input is None:
            return model_route.model_copy(update={"suggested_review_input": _suggest_review_input(input.request)})
        return model_route


INTAKE_ROUTER = register_step(IntakeRouterStep())


def _suggest_review_input(request: str) -> dict:
    """Extract a best-effort ReviewOnlyInput hint from the request."""
    text = request.strip()
    lower = text.lower()
    files = _extract_review_files(text)
    if files:
        return {"input_kind": "file_list", "files_to_review": files}
    if any(marker in text for marker in PASTED_CODE_MARKERS) or "pasted" in lower or "paste" in lower:
        return {"input_kind": "pasted_text"}
    return {"input_kind": "workspace_diff", "diff_base": "HEAD"}


def _extract_review_files(request: str) -> list[str]:
    """Find simple file path references in a review request."""
    matches = re.findall(
        r"(?<![\w.-])([\w./\\-]+\.(?:py|md|toml|json|yaml|yml|txt|rst|ini|cfg))(?![\w.-])",
        request,
    )
    seen: set[str] = set()
    files: list[str] = []
    for match in matches:
        normalized = match.replace("\\", "/").strip(".,;:)")
        if normalized and normalized not in seen:
            seen.add(normalized)
            files.append(normalized)
    return files
