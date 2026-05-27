from __future__ import annotations

from collections.abc import Iterable

from agentscope.credential import CredentialBase
from agentscope.model import ChatModelBase, ChatResponse
from agentscope.message import TextBlock, ToolCallBlock
from pydantic import BaseModel


class ScriptedCredential(CredentialBase):
    @classmethod
    def get_chat_model_class(cls):
        return ScriptedChatModel


class ScriptedChatModel(ChatModelBase):
    class Parameters(BaseModel):
        pass

    def __init__(self, responses: Iterable[ChatResponse]):
        super().__init__(
            credential=ScriptedCredential(),
            model="scripted-poc-model",
            parameters=self.Parameters(),
            stream=False,
            max_retries=1,
            context_size=4096,
        )
        self._responses = list(responses)

    async def _call_api(self, model_name, messages, tools=None, tool_choice=None, **kwargs):
        if not self._responses:
            return text_response("done")
        return self._responses.pop(0)


def text_response(text: str) -> ChatResponse:
    return ChatResponse(content=[TextBlock(text=text)], is_last=True)


def tool_response(tool_id: str, name: str, json_input: str) -> ChatResponse:
    return ChatResponse(
        content=[
            ToolCallBlock(
                id=tool_id,
                name=name,
                input=json_input,
            ),
        ],
        is_last=True,
    )


def joined_text(blocks) -> str:
    parts: list[str] = []
    for block in blocks:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(parts)
