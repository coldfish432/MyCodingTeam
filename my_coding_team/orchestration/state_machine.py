"""Minimal PM state-machine validation."""

from __future__ import annotations


ALLOWED_TRANSITIONS = {
    "initialized": {"routed", "blocked"},
    "routed": {"direct_answer", "workspace_prepared", "blocked"},
    "direct_answer": {"delivered", "blocked"},
    "workspace_prepared": {"context_collected", "blocked"},
    "context_collected": {"planned", "blocked"},
    "planned": {"implemented", "blocked"},
    "implemented": {"verified", "blocked"},
    "verified": {"reviewed", "blocked"},
    "reviewed": {"delivered", "blocked"},
    "blocked": set(),
    "delivered": set(),
}


def transition(current: str, target: str) -> str:
    """校验并执行一次 PM 状态转换。

    参数：
        current: 当前状态名。
        target: 目标状态名。

    返回：
        合法的目标状态名。

    异常：
        ValueError: 状态转换不在允许表中。
    """
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"Illegal state transition: {current} -> {target}")
    return target
