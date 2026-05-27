"""Prompt loading helpers."""

from __future__ import annotations

from pathlib import Path


PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


class PromptNotFoundError(FileNotFoundError):
    """请求的 prompt 文件不存在。"""

    pass


def load_prompt(name: str) -> str:
    """按名称加载 prompts 目录下的 Markdown prompt。

    参数：
        name: 不带 `.md` 后缀的 prompt 名称。

    返回：
        prompt 文件内容。

    异常：
        PromptNotFoundError: prompt 文件不存在。
    """
    path = PROMPT_DIR / f"{name}.md"
    if not path.exists():
        raise PromptNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")
