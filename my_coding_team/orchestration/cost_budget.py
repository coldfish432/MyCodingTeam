"""Cost budget helpers for orchestration."""

from __future__ import annotations

from dataclasses import dataclass


class BudgetExceededError(RuntimeError):
    """LLM 调用预算耗尽时抛出的阻断错误。"""

    pass


@dataclass
class LlmBudget:
    """编排层使用的 LLM 调用预算计数器。"""

    limit: int
    used: int = 0

    def charge(self, amount: int = 1) -> None:
        """扣减预算，超限时抛出 BudgetExceededError。

        参数：
            amount: 本次消耗调用数。

        返回：
            None。
        """
        if self.used + amount > self.limit:
            raise BudgetExceededError("blocked_by_budget_exceeded")
        self.used += amount
