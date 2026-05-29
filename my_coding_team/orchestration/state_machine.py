"""Minimal PM state-machine validation."""

from __future__ import annotations


ALLOWED_TRANSITIONS = {
    "initialized": {"routed", "blocked"},
    "routed": {"direct_answer", "workspace_prepared", "shaping", "blocked"},
    "direct_answer": {"delivered", "blocked"},
    "shaping": {"specifying", "blocked"},
    "specifying": {"awaiting_design_signoff", "blocked"},
    "awaiting_design_signoff": {"planning_task_queue", "blocked_by_user_decision", "blocked"},
    "workspace_prepared": {"context_collected", "blocked"},
    "context_collected": {"planned", "planning_task_queue", "reviewing_readonly", "blocked"},
    "planned": {"writing_red", "implemented", "blocked", "blocked_by_red_mismatch"},
    "planning_task_queue": {"workspace_prepared", "executing_task", "blocked"},
    "writing_red": {"implemented", "blocked", "blocked_by_red_mismatch"},
    "implemented": {"verified", "blocked"},
    "executing_task": {"final_verifying", "blocked", "blocked_by_red_mismatch"},
    "verified": {"reviewed", "blocked"},
    "reviewed": {"delivered", "blocked"},
    "reviewing_readonly": {"delivered", "blocked"},
    "final_verifying": {"final_reviewing", "blocked"},
    "final_reviewing": {"global_repairing", "finishing_branch", "delivered", "blocked"},
    "global_repairing": {"final_verifying", "blocked_by_max_repair_retries_exceeded"},
    "finishing_branch": {"delivered", "blocked"},
    "blocked": set(),
    "blocked_by_user_decision": set(),
    "blocked_by_red_mismatch": set(),
    "blocked_by_max_repair_retries_exceeded": set(),
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
