from agentscope.agent import Agent
from agentscope.message import ToolResultState
from agentscope.message import UserMsg
from agentscope.permission import PermissionContext, PermissionMode
from agentscope.state import AgentState
from agentscope.tool import Bash, Toolkit

from .helpers import ScriptedChatModel, joined_text, text_response, tool_response


async def test_agent_reply_can_execute_read_only_bash_in_default_mode():
    agent = Agent(
        name="PocAgentBasics",
        system_prompt="Use tools when asked.",
        model=ScriptedChatModel(
            [
                tool_response(
                    "bash-1",
                    "Bash",
                    '{"command": "cd", "description": "Show working directory"}',
                ),
                text_response("observed pwd"),
            ],
        ),
        toolkit=Toolkit(tools=[Bash()]),
    )

    events = [
        event
        async for event in agent.reply_stream(UserMsg(name="user", content="run cwd"))
    ]
    deltas = [
        event.delta
        for event in events
        if getattr(event, "type", None) == "TOOL_RESULT_TEXT_DELTA"
    ]
    result_states = [
        event.state
        for event in events
        if getattr(event, "type", None) == "TOOL_RESULT_END"
    ]

    assert ToolResultState.SUCCESS in result_states
    assert any("D:\\Mycode\\myCodingTeam" in delta for delta in deltas)


async def test_explore_mode_denies_bash_even_for_read_only_command():
    agent = Agent(
        name="PocExploreBashAgent",
        system_prompt="Use tools when asked.",
        model=ScriptedChatModel(
            [
                tool_response(
                    "bash-explore-1",
                    "Bash",
                    '{"command": "cd", "description": "Show working directory"}',
                ),
                text_response("explore bash denied"),
            ],
        ),
        toolkit=Toolkit(tools=[Bash()]),
        state=AgentState(
            permission_context=PermissionContext(mode=PermissionMode.EXPLORE),
        ),
    )

    events = [
        event
        async for event in agent.reply_stream(UserMsg(name="user", content="run cwd"))
    ]
    deltas = [
        event.delta
        for event in events
        if getattr(event, "type", None) == "TOOL_RESULT_TEXT_DELTA"
    ]
    result_states = [
        event.state
        for event in events
        if getattr(event, "type", None) == "TOOL_RESULT_END"
    ]

    assert ToolResultState.DENIED in result_states
    assert any("explore mode is read-only" in delta for delta in deltas)
