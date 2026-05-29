"""Materialize review-only inputs into text for ReviewRoom."""

from __future__ import annotations

import subprocess
from pathlib import Path

from my_coding_team.schemas.workflow import ReviewOnlyInput, WorkspaceRecord


async def materialize_review_input(input_spec: ReviewOnlyInput, workspace: WorkspaceRecord | str | Path) -> str:
    """Convert a ReviewOnlyInput into a text blob for read-only review."""
    root = _workspace_root(workspace)
    if input_spec.input_kind == "file_list":
        return _read_files_as_blob(input_spec.files_to_review, root)
    if input_spec.input_kind == "workspace_diff":
        return _run_git_diff(input_spec.diff_base, input_spec.diff_target, root)
    if input_spec.input_kind == "pasted_text":
        return input_spec.pasted_content or ""
    raise ValueError(f"Unknown input_kind: {input_spec.input_kind}")


def summarize_review_input(input_spec: ReviewOnlyInput, target_blob: str) -> str:
    """Build a short human-readable description of the review target."""
    if input_spec.input_kind == "file_list":
        count = len(input_spec.files_to_review)
        head = ", ".join(input_spec.files_to_review[:3])
        suffix = f" (+{count - 3} more)" if count > 3 else ""
        noun = "file" if count == 1 else "files"
        return f"{head}{suffix} ({count} {noun})"
    if input_spec.input_kind == "workspace_diff":
        base = input_spec.diff_base or "HEAD"
        target = input_spec.diff_target or "working tree"
        return f"{base} vs {target} ({target_blob.count(chr(10))} lines)"
    if input_spec.input_kind == "pasted_text":
        hint = input_spec.pasted_language_hint or "unknown"
        lines = target_blob.count("\n") + (1 if target_blob else 0)
        return f"pasted {hint} ({lines} lines)"
    return "unknown review input"


def _workspace_root(workspace: WorkspaceRecord | str | Path) -> Path:
    if isinstance(workspace, WorkspaceRecord):
        return Path(workspace.root)
    return Path(workspace)


def _read_files_as_blob(files: list[str], root: Path) -> str:
    parts: list[str] = []
    for file_name in files:
        path = (root / file_name).resolve()
        if not _is_relative_to(path, root.resolve()):
            raise PermissionError(f"review target is outside workspace: {file_name}")
        if not path.exists() or not path.is_file():
            parts.append(f"=== FILE: {file_name} ===\n[missing file]\n")
            continue
        parts.append(f"=== FILE: {file_name} ===\n{path.read_text(encoding='utf-8')}\n")
    return "\n".join(parts)


def _run_git_diff(base: str | None, target: str | None, root: Path) -> str:
    args = ["git", "diff", base or "HEAD"]
    if target:
        args.append(target)
    result = subprocess.run(args, cwd=root, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff failed")
    return result.stdout


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
