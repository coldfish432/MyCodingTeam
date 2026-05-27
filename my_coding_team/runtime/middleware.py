"""Lightweight runtime helpers for schema parsing, logging, and budgets."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, TypeVar

from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


def parse_schema(schema_class: type[T], payload: str | dict[str, Any]) -> T:
    """把模型输出解析成指定 Pydantic schema。

    参数：
        schema_class: 目标 Pydantic 模型类。
        payload: JSON 字符串或 dict。

    返回：
        已校验的 schema 实例。
    """
    if isinstance(payload, str):
        return schema_class.model_validate_json(payload)
    return schema_class.model_validate(payload)


@dataclass
class RuntimeLog:
    """内存运行日志，供测试和后续持久化层复用。"""

    records: list[dict[str, Any]] = field(default_factory=list)

    def add(self, event: str, **fields: Any) -> None:
        """追加一条带 UTC 时间戳的事件记录。

        参数：
            event: 事件名。
            **fields: 事件附加字段。

        返回：
            None。
        """
        self.records.append(
            {
                "event": event,
                "time": datetime.now(timezone.utc).isoformat(),
                **fields,
            },
        )


@dataclass
class CostBudget:
    """简单 LLM 调用预算计数器。"""

    limit: int
    used: int = 0

    def charge(self, amount: int = 1) -> None:
        """消耗预算，超限时阻断。

        参数：
            amount: 本次消耗数量。

        返回：
            None。

        异常：
            RuntimeError: 预算不足。
        """
        if self.used + amount > self.limit:
            raise RuntimeError("blocked_by_budget_exceeded")
        self.used += amount


def dumps_for_prompt(value: BaseModel | dict[str, Any]) -> str:
    """把 schema 或 dict 转成适合放入 prompt 的 JSON 文本。

    参数：
        value: Pydantic 模型或普通 dict。

    返回：
        缩进后的 JSON 字符串。
    """
    if isinstance(value, BaseModel):
        return value.model_dump_json(indent=2)
    return json.dumps(value, indent=2)
