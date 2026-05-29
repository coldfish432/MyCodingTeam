"""Step abstraction: output-fixed computation unit."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class StepContext(BaseModel):
    """Runtime context passed to Step.run()."""

    model_config = {"arbitrary_types_allowed": True}

    workspace_root: str | None = None
    model: Any = None
    llm_call_charge: int = 0


class Step(ABC, Generic[InputT, OutputT]):
    """Base class for output-fixed computation units."""

    name: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]

    @abstractmethod
    async def run(self, input: InputT, context: StepContext) -> OutputT:
        """Execute the step and return output_schema."""
        ...


class PythonStep(Step[InputT, OutputT]):
    """A Step implemented in pure Python."""

    pass


class LLMBackedStep(Step[InputT, OutputT]):
    """A Step that uses a single Agent or model call to fill a schema."""

    @abstractmethod
    def build_prompt_input(self, input: InputT) -> str:
        """Convert typed input to LLM message text."""
        ...

    @abstractmethod
    def make_agent(self, context: StepContext) -> Any:
        """Construct the backing agent or model facade for this step."""
        ...
