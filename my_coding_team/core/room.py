"""Room abstraction: multi-Agent collaboration unit."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel

from my_coding_team.core.step import StepContext

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class Room(ABC, Generic[InputT, OutputT]):
    """Base class for collaboration units with structured output."""

    name: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]

    @abstractmethod
    async def execute(self, input: InputT, context: StepContext) -> OutputT:
        """Convene the Room and produce the structured outcome."""
        ...
