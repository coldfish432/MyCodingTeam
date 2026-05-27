"""OpenAI-compatible model client using only the standard library."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from my_coding_team.config import AppConfig, load_config


class ModelConfigurationError(RuntimeError):
    """模型配置缺失或不完整时抛出的错误。"""

    pass


@dataclass
class OpenAICompatibleModel:
    """基于标准库 urllib 的 OpenAI-compatible 聊天模型客户端。

    字段：
        config: 应用配置，提供模型名和 base URL。
        timeout_seconds: HTTP 请求超时时间。
    """

    config: AppConfig
    timeout_seconds: int = 60

    @classmethod
    def from_env(cls) -> "OpenAICompatibleModel":
        """从当前工作目录 .env 和环境变量创建模型客户端。

        参数：
            无。

        返回：
            OpenAICompatibleModel。

        异常：
            ModelConfigurationError: 缺少模型名、base URL 或 API key。
        """
        config = load_config()
        if not config.model_name or not config.model_base_url or not config.has_model_api_key:
            raise ModelConfigurationError("LLM_MODEL, LLM_BASE_URL, and LLM_API_KEY are required")
        return cls(config=config)

    async def complete_text(self, prompt: str) -> str:
        """请求模型返回普通文本。

        参数：
            prompt: 用户 prompt。

        返回：
            模型返回的 message content。
        """
        data = self._post_chat(prompt)
        return data["choices"][0]["message"]["content"]

    async def complete_json(self, prompt: str) -> dict[str, Any]:
        """请求模型返回 JSON 对象。

        参数：
            prompt: 用户 prompt；方法会追加只返回 JSON 的约束。

        返回：
            解析后的 JSON object。
        """
        text = await self.complete_text(
            f"{prompt}\n\nReturn only valid JSON. Do not wrap it in markdown.",
        )
        return _loads_json_object(text)

    def _post_chat(self, prompt: str) -> dict[str, Any]:
        """向 OpenAI-compatible `/chat/completions` 端点发送请求。

        参数：
            prompt: 用户 prompt。

        返回：
            API 响应 JSON。
        """
        api_key = _api_key_from_config()
        base_url = (self.config.model_base_url or "").rstrip("/")
        url = f"{base_url}/chat/completions"
        body = json.dumps(
            {
                "model": self.config.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
        ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Model request failed: {exc}") from exc


def _api_key_from_config() -> str:
    """从环境变量或当前目录 .env 中读取 API key。

    参数：
        无。

    返回：
        API key 字符串；调用方不得打印。
    """
    import os
    from pathlib import Path

    env = dict(os.environ)
    dotenv = Path.cwd() / ".env"
    if dotenv.exists():
        for raw in dotenv.read_text(encoding="utf-8").splitlines():
            if "=" in raw and not raw.strip().startswith("#"):
                key, value = raw.split("=", 1)
                env.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    key = env.get("MY_CODING_TEAM_API_KEY") or env.get("LLM_API_KEY")
    if not key:
        raise ModelConfigurationError("Missing API key")
    return key


def _loads_json_object(text: str) -> dict[str, Any]:
    """解析模型返回的 JSON object，并兼容 markdown fence。

    参数：
        text: 模型原始文本。

    返回：
        dict JSON object。
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    data = json.loads(stripped)
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object from model")
    return data
