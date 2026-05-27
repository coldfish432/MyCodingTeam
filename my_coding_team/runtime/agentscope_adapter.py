"""Narrow import adapter for AgentScope v2.

Business modules should import AgentScope symbols from here so the rest of the
codebase has a single boundary to update if the runtime API shifts.
"""

from __future__ import annotations

from agentscope.agent import Agent
from agentscope.credential import CredentialBase
from agentscope.model import ChatModelBase, ChatResponse
from agentscope.message import TextBlock, ToolCallBlock, UserMsg
from agentscope.permission import (
    PermissionBehavior,
    PermissionContext,
    PermissionMode,
    PermissionRule,
)
from agentscope.state import AgentState
from agentscope.tool import Bash, Edit, Glob, Grep, Read, Toolkit, Write
from agentscope.workspace import DockerWorkspace, LocalWorkspace

__all__ = [
    "Agent",
    "AgentState",
    "Bash",
    "ChatModelBase",
    "ChatResponse",
    "CredentialBase",
    "DockerWorkspace",
    "Edit",
    "Glob",
    "Grep",
    "LocalWorkspace",
    "PermissionBehavior",
    "PermissionContext",
    "PermissionMode",
    "PermissionRule",
    "Read",
    "TextBlock",
    "Toolkit",
    "ToolCallBlock",
    "UserMsg",
    "Write",
]
