"""Branch Finisher — 根据工作区和交付状态给出处置建议，不执行 destructive 操作。"""

from __future__ import annotations

from typing import Literal

from my_coding_team.schemas.delivery import FinishDecision
from my_coding_team.schemas.review import FinalReviewReport
from my_coding_team.schemas.task import VerificationResult
from my_coding_team.schemas.workflow import WorkspaceRecord


FinishAction = Literal[
    "report_only",
    "open_pr",
    "keep_branch_for_user_review",
    "keep_worktree_for_follow_up",
    "discard_experimental_changes",
]


class BranchFinishDecision:
    """分支处置建议，不执行 destructive 操作。"""

    def __init__(
        self,
        *,
        action: FinishAction,
        reason: str,
        suggested_commands: list[str] | None = None,
    ) -> None:
        self.action = action
        self.reason = reason
        self.suggested_commands = suggested_commands or []


def decide_branch_finish(
    workspace: WorkspaceRecord,
    final_verification: VerificationResult | None,
    final_review: FinalReviewReport | None,
) -> BranchFinishDecision:
    """根据最终状态给出分支处置建议。

    参数：
        workspace: 工作区状态快照。
        final_verification: 最终验证结果。
        final_review: 最终审查报告。

    返回：
        BranchFinishDecision，只建议不执行。
    """
    # 验证失败或 review 有 must_fix → 保留让用户检查
    if final_verification and not final_verification.passed:
        return BranchFinishDecision(
            action="keep_worktree_for_follow_up",
            reason="Final verification did not pass; keep worktree for user inspection.",
            suggested_commands=["git diff", "git status"],
        )

    if final_review and not final_review.approval:
        return BranchFinishDecision(
            action="keep_branch_for_user_review",
            reason="Final review found blocking issues; keep branch for user review.",
            suggested_commands=["git diff HEAD~1", "pytest"],
        )

    # 工作区 dirty → 建议 commit 但不强行操作
    if workspace.dirty_files:
        return BranchFinishDecision(
            action="keep_worktree_for_follow_up",
            reason=f"Dirty files: {', '.join(workspace.dirty_files[:5])}",
            suggested_commands=["git add -A", "git commit -m 'Phase 9 Full Flow changes'", "git push"],
        )

    # 一切通过 → 建议提 PR
    if workspace.is_git:
        return BranchFinishDecision(
            action="open_pr",
            reason="All checks passed; ready for PR.",
            suggested_commands=["git push", "# open PR on GitHub/GitLab"],
        )

    # 非 Git 仓库
    return BranchFinishDecision(
        action="report_only",
        reason="Not a Git repository; changes are on disk only.",
        suggested_commands=[],
    )
