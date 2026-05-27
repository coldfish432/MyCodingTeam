from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    """应用运行时配置。

    字段：
        model_provider: 模型提供方标识。
        model_name: 真实 LLM 模型名。
        model_base_url: OpenAI-compatible API base URL。
        has_model_api_key: 是否已配置 API key，仅暴露布尔值避免泄密。
        log_dir: 日志目录。
        default_workspace: 默认工作区目录。
    """

    model_provider: str | None
    model_name: str | None
    model_base_url: str | None
    has_model_api_key: bool
    log_dir: str
    default_workspace: str


def _read_dotenv(path: Path) -> dict[str, str]:
    """读取简单 KEY=VALUE 形式的 .env 文件。

    参数：
        path: .env 文件路径。

    返回：
        解析后的键值字典；文件不存在时返回空字典。
    """
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_config(env: dict[str, str] | None = None, cwd: str | Path | None = None) -> AppConfig:
    """加载运行时配置，优先级为显式 env 覆盖 .env。

    参数：
        env: 测试或调用方传入的环境变量覆盖。
        cwd: 配置解析基准目录；为空时使用当前工作目录。

    返回：
        AppConfig。不会返回明文 API key。
    """
    base_dir = Path(cwd) if cwd is not None else Path.cwd()
    dotenv_values = _read_dotenv(base_dir / ".env")
    source = {**dotenv_values, **(env if env is not None else os.environ)}

    log_dir = source.get("MY_CODING_TEAM_LOG_DIR")
    default_workspace = source.get("MY_CODING_TEAM_WORKSPACE")
    model_name = source.get("MY_CODING_TEAM_MODEL_NAME") or source.get("LLM_MODEL")
    model_base_url = source.get("MY_CODING_TEAM_MODEL_BASE_URL") or source.get("LLM_BASE_URL")
    has_model_api_key = bool(source.get("MY_CODING_TEAM_API_KEY") or source.get("LLM_API_KEY"))
    model_provider = source.get("MY_CODING_TEAM_MODEL_PROVIDER")
    if model_provider is None and (model_name or model_base_url or has_model_api_key):
        model_provider = "openai_compatible"

    return AppConfig(
        model_provider=model_provider,
        model_name=model_name,
        model_base_url=model_base_url,
        has_model_api_key=has_model_api_key,
        log_dir=str(Path(log_dir).expanduser()) if log_dir else str(base_dir / ".my_coding_team" / "logs"),
        default_workspace=str(Path(default_workspace).expanduser()) if default_workspace else str(base_dir),
    )
