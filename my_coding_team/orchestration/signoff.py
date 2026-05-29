"""Design Signoff CLI — 用户确认 ProductBrief 的阶段门。"""

from __future__ import annotations

import sys
import os

from my_coding_team.schemas.workflow import DesignSignoff, ProductBrief


def request_design_signoff_cli(brief: ProductBrief) -> DesignSignoff:
    """最简 CLI signoff：打印 ProductBrief，读 stdin Y/N/A。

    Y: approve as-is
    A: approve, 但把所有 open_questions 转成 assumptions
    N: reject

    非交互环境（无 tty）走 auto-approve 不破坏测试/CI。

    参数：
        brief: Specification 输出的 ProductBrief。

    返回：
        DesignSignoff，包含 permission_to_plan 和相关元信息。
    """
    print("\n" + "=" * 60)
    print("DESIGN SIGNOFF REQUIRED")
    print("=" * 60)
    print(f"\nTitle: {brief.title}")
    print(f"Summary: {brief.summary}")

    print("\nGoals:")
    for item in brief.goals:
        print(f"  - {item}")

    print("\nNon-goals:")
    for item in brief.non_goals:
        print(f"  - {item}")

    if brief.requirements:
        print("\nRequirements:")
        for item in brief.requirements:
            print(f"  - {item}")

    if brief.acceptance_criteria:
        print("\nAcceptance criteria:")
        for item in brief.acceptance_criteria:
            print(f"  - {item}")

    if brief.assumptions:
        print("\nAssumptions:")
        for item in brief.assumptions:
            print(f"  - {item}")

    if brief.open_questions:
        print("\nOpen questions:")
        for item in brief.open_questions:
            print(f"  ? {item}")

    print("\n" + "-" * 60)

    simulated_choice = os.environ.get("MY_CODING_TEAM_SIGNOFF_CHOICE")
    if simulated_choice:
        print(f"[simulated signoff choice: {simulated_choice}]")
        return _signoff_from_choice(
            brief,
            simulated_choice,
            reject_reason=os.environ.get("MY_CODING_TEAM_SIGNOFF_REASON"),
        )

    if not sys.stdin.isatty():
        print("[non-interactive environment detected, auto-approving]")
        return _auto_approve(brief)

    while True:
        try:
            choice = input(
                "Approve? [Y]es / [A]pprove with all open questions as assumptions / [N]o: "
            ).strip().lower()
        except EOFError:
            print("[stdin EOF detected, auto-approving]")
            return _auto_approve(brief)

        if choice in ("y", "yes", "a", "assume"):
            return _signoff_from_choice(brief, choice)
        if choice in ("n", "no"):
            reason = input("Reason (optional): ").strip() or "user_rejected"
            return _signoff_from_choice(brief, choice, reject_reason=reason)
        print("Please enter Y, A, or N.")


def _auto_approve(brief: ProductBrief) -> DesignSignoff:
    return DesignSignoff(
        permission_to_plan=True,
        approved_by="auto_signoff_non_interactive",
        approved_direction=brief.title,
        approved_scope=list(brief.goals),
        accepted_assumptions=list(brief.assumptions),
        reason="auto_approved_non_interactive",
        notes=f"ProductBrief: {brief.title}",
    )


def _signoff_from_choice(
    brief: ProductBrief,
    choice: str,
    *,
    reject_reason: str | None = None,
) -> DesignSignoff:
    normalized = choice.strip().lower()
    if normalized in ("y", "yes"):
        return DesignSignoff(
            permission_to_plan=True,
            approved_by="user",
            approved_direction=brief.title,
            approved_scope=list(brief.goals),
            accepted_assumptions=list(brief.assumptions),
            reason="user_approved",
            notes=f"ProductBrief: {brief.title}",
        )
    if normalized in ("a", "assume"):
        return DesignSignoff(
            permission_to_plan=True,
            approved_by="user",
            approved_direction=brief.title,
            approved_scope=list(brief.goals),
            accepted_assumptions=list(brief.assumptions) + list(brief.open_questions),
            reason="user_approved_with_questions_as_assumptions",
            notes=f"ProductBrief: {brief.title}, open_questions converted to assumptions",
        )
    if normalized in ("n", "no"):
        return DesignSignoff(
            permission_to_plan=False,
            approved_by="user",
            reason=reject_reason or "user_rejected",
            notes="user_rejected_signoff",
        )
    raise ValueError("MY_CODING_TEAM_SIGNOFF_CHOICE must be one of y, yes, a, assume, n, no")
