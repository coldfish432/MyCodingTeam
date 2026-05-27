"""Deterministic model implementations for tests and local dry runs."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel

from my_coding_team.runtime.agentscope_adapter import (
    ChatModelBase,
    ChatResponse,
    CredentialBase,
    TextBlock,
    ToolCallBlock,
)


class ScriptedCredential(CredentialBase):
    """AgentScope 测试模型使用的凭证占位类。"""

    @classmethod
    def get_chat_model_class(cls):
        """返回与该凭证绑定的 ChatModelBase 子类。"""
        return ScriptedChatModel


class ScriptedChatModel(ChatModelBase):
    """按脚本顺序返回 ChatResponse 的 AgentScope 测试模型。"""

    class Parameters(BaseModel):
        """ScriptedChatModel 不需要额外参数。"""

        pass

    def __init__(self, responses: Iterable[ChatResponse]):
        """初始化脚本响应队列。

        参数：
            responses: 预先准备的 ChatResponse 序列。
        """
        super().__init__(
            credential=ScriptedCredential(),
            model="scripted-mvp-model",
            parameters=self.Parameters(),
            stream=False,
            max_retries=1,
            context_size=4096,
        )
        self._responses = list(responses)

    async def _call_api(self, model_name, messages, tools=None, tool_choice=None, **kwargs):
        """模拟 AgentScope 底层 API 调用。

        参数：
            model_name: AgentScope 传入的模型名。
            messages: 当前上下文消息。
            tools: 可用工具列表。
            tool_choice: 工具选择策略。
            **kwargs: 其他运行时参数。

        返回：
            下一条脚本响应；耗尽后返回 `done` 文本。
        """
        if not self._responses:
            return text_response("done")
        return self._responses.pop(0)


def text_response(text: str) -> ChatResponse:
    """构建 AgentScope 文本响应。

    参数：
        text: 响应文本。

    返回：
        ChatResponse，content 中包含 TextBlock。
    """
    return ChatResponse(content=[TextBlock(text=text)], is_last=True)


def tool_response(tool_id: str, name: str, json_input: str) -> ChatResponse:
    """构建 AgentScope 工具调用响应。

    参数：
        tool_id: 工具调用 ID。
        name: 工具名称。
        json_input: 工具输入 JSON 字符串。

    返回：
        ChatResponse，content 中包含 ToolCallBlock。
    """
    return ChatResponse(content=[ToolCallBlock(id=tool_id, name=name, input=json_input)], is_last=True)


class DeterministicModel:
    """Small structured model used by unit tests and deterministic flows."""

    def __init__(
        self,
        *,
        text: str = "done",
        json_outputs: Iterable[dict[str, Any]] | None = None,
    ) -> None:
        """初始化确定性模型。

        参数：
            text: complete_text 固定返回文本。
            json_outputs: complete_json 依次返回的 JSON 对象。
        """
        self.text = text
        self._json_outputs = list(json_outputs or [])
        self.calls = 0

    async def complete_text(self, prompt: str) -> str:
        """返回固定文本并记录调用次数。

        参数：
            prompt: 调用方 prompt，当前实现不解析。

        返回：
            初始化时提供的 text。
        """
        self.calls += 1
        return self.text

    async def complete_json(self, prompt: str) -> dict[str, Any]:
        """按队列返回固定 JSON 对象并记录调用次数。

        参数：
            prompt: 调用方 prompt，当前实现不解析。

        返回：
            下一条 JSON；队列为空时返回空 dict。
        """
        self.calls += 1
        if self._json_outputs:
            return self._json_outputs.pop(0)
        return {}
