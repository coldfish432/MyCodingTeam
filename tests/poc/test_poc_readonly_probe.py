from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from agentscope.agent import Agent
from agentscope.message import ToolResultState, UserMsg
from agentscope.permission import PermissionContext, PermissionMode
from agentscope.state import AgentState
from agentscope.tool import Bash, Glob, Grep, Read, Toolkit

from my_coding_team.orchestration.permission_builder import (
    build_readonly_probe_deny_rules,
    build_readonly_probe_rules,
)

from .helpers import ScriptedChatModel, text_response, tool_response


def _make_agent(command: str) -> Agent:
    return Agent(
        name="ReadonlyProbePOC",
        system_prompt="Read-only probe POC agent.",
        model=ScriptedChatModel(
            [
                tool_response(
                    "readonly-probe-bash",
                    "Bash",
                    json.dumps(
                        {
                            "command": command,
                            "description": "Run read-only probe command",
                        },
                    ),
                ),
                text_response("done"),
            ],
        ),
        toolkit=Toolkit(tools=[Read(), Grep(), Glob(), Bash()]),
        state=AgentState(
            permission_context=PermissionContext(
                mode=PermissionMode.DONT_ASK,
                allow_rules=build_readonly_probe_rules(),
                deny_rules=build_readonly_probe_deny_rules(),
                working_directories={},
            ),
        ),
    )


async def _collect_events(agent: Agent, prompt: str) -> list:
    return [event async for event in agent.reply_stream(UserMsg(name="user", content=prompt))]


def _tool_result_states(events) -> list[ToolResultState | str]:
    return [
        event.state
        for event in events
        if getattr(event, "type", None) == "TOOL_RESULT_END"
    ]


def _tool_result_text(events) -> str:
    return "\n".join(
        event.delta
        for event in events
        if getattr(event, "type", None) == "TOOL_RESULT_TEXT_DELTA"
    )


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "poc@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "poc"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("poc\n", encoding="utf-8")
    return tmp_path


@pytest.mark.asyncio
async def test_whitelisted_readonly_command_is_allowed(git_repo: Path):
    cwd = os.getcwd()
    os.chdir(git_repo)
    try:
        events = await _collect_events(_make_agent("git status --short"), "probe status")
    finally:
        os.chdir(cwd)

    assert ToolResultState.SUCCESS in _tool_result_states(events)
    assert "README.md" in _tool_result_text(events)
    assert "Permission denied" not in _tool_result_text(events)


@pytest.mark.asyncio
async def test_destructive_command_is_denied(tmp_path: Path):
    victim = tmp_path / "must_survive.txt"
    victim.write_text("alive\n", encoding="utf-8")

    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        events = await _collect_events(_make_agent(f"rm -rf {victim}"), "try to delete")
    finally:
        os.chdir(cwd)

    assert ToolResultState.DENIED in _tool_result_states(events)
    assert "permission" in _tool_result_text(events).lower()
    assert "denied" in _tool_result_text(events).lower()
    assert victim.exists()
    assert victim.read_text(encoding="utf-8") == "alive\n"


@pytest.mark.asyncio
async def test_non_whitelisted_git_subcommand_is_denied(git_repo: Path):
    cwd = os.getcwd()
    os.chdir(git_repo)
    try:
        events = await _collect_events(_make_agent("git checkout main"), "try to checkout")
    finally:
        os.chdir(cwd)

    assert ToolResultState.DENIED in _tool_result_states(events)
    assert "permission" in _tool_result_text(events).lower()
    assert "denied" in _tool_result_text(events).lower()
