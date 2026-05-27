from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import platform
import sys

from . import __version__
from .config import AppConfig, load_config
from .orchestration.pm_orchestrator import run_request
from .runtime.llm_client import ModelConfigurationError, OpenAICompatibleModel
from .runtime.mock_model import DeterministicModel


def _version_status(package_name: str, minimum_major: int | None = None) -> tuple[bool, str]:
    """检查依赖包是否安装且满足最低主版本。

    参数：
        package_name: Python distribution 名称。
        minimum_major: 可选最低主版本。

    返回：
        (是否通过, 面向 CLI 的状态文本)。
    """
    try:
        version = importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return False, f"{package_name}: not installed"

    if minimum_major is not None:
        major_text = version.split(".", 1)[0]
        try:
            major = int(major_text)
        except ValueError:
            return False, f"{package_name}: installed ({version}), cannot parse major version"
        if major < minimum_major:
            return False, f"{package_name}: installed ({version}), requires >= {minimum_major}.0"

    return True, f"{package_name}: {version}"


def run_doctor(config: AppConfig | None = None) -> int:
    """运行本地环境健康检查。

    参数：
        config: 可选 AppConfig，测试中用于注入配置。

    返回：
        进程退出码；全部检查通过返回 0。
    """
    config = config or load_config()
    checks: list[tuple[bool, str]] = []

    checks.append((sys.version_info >= (3, 11), f"python: {platform.python_version()}"))
    checks.append(_version_status("pydantic", minimum_major=2))
    checks.append(_version_status("agentscope", minimum_major=2))

    print("My Coding Team doctor")
    print(f"version: {__version__}")
    print(f"model_provider: {config.model_provider or 'not configured'}")
    print(f"model_name: {config.model_name or 'not configured'}")
    print(f"log_dir: {config.log_dir}")
    print(f"default_workspace: {config.default_workspace}")
    print()

    for passed, message in checks:
        prefix = "OK" if passed else "ERROR"
        print(f"{prefix}: {message}")

    return 0 if all(passed for passed, _ in checks) else 1


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    参数：
        无。

    返回：
        配置好 doctor、config、run 子命令的 ArgumentParser。
    """
    parser = argparse.ArgumentParser(
        prog="my-coding-team",
        description="Run and inspect the My Coding Team workflow system.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("doctor", help="Check local runtime and dependency readiness.")
    subparsers.add_parser("config", help="Print resolved non-secret configuration.")
    run_parser = subparsers.add_parser("run", help="Run an MVP workflow request.")
    run_parser.add_argument("request", help="User request to run.")
    run_parser.add_argument("--budget", type=int, default=10, help="LLM call budget.")
    run_parser.add_argument("--workspace", default=None, help="Workspace path. Defaults to current directory.")
    run_parser.add_argument(
        "--mode",
        choices=["auto", "direct", "lightweight"],
        default="auto",
        help="Workflow routing mode.",
    )
    run_parser.add_argument("--mock", action="store_true", help="Use deterministic local model instead of .env API.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 入口函数。

    参数：
        argv: 可选参数列表；为空时由 argparse 使用 sys.argv。

    返回：
        进程退出码。
    """
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    if args.command == "doctor":
        return run_doctor()

    if args.command == "config":
        config = load_config()
        for key, value in config.__dict__.items():
            print(f"{key}: {value}")
        return 0

    if args.command == "run":
        try:
            model = DeterministicModel(text="Mock direct answer.") if args.mock else OpenAICompatibleModel.from_env()
            package = asyncio.run(
                run_request(
                    args.request,
                    budget=args.budget,
                    workspace=args.workspace,
                    mode=args.mode,
                    model=model,
                ),
            )
        except ModelConfigurationError as exc:
            print(f"ERROR: {exc}")
            return 2
        print(package.model_dump_json(indent=2))
        return 0 if package.decision.status == "success" else 1

    parser.print_help()
    return 0
