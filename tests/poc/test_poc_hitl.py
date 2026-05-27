import json

from agentscope.agent import Agent
from agentscope.event import ConfirmResult, RequireUserConfirmEvent, UserConfirmResultEvent
from agentscope.message import ToolResultState, UserMsg
from agentscope.tool import Bash, Toolkit

from .helpers import ScriptedChatModel, joined_text, text_response, tool_response


async def test_reply_stream_can_resume_after_user_confirmation(tmp_path):
    target_dir = tmp_path / "confirmed-dir"
    command = f'mkdir "{target_dir}"'
    agent = Agent(
        name="PocHitlAgent",
        system_prompt="Ask before non-read-only shell commands.",
        model=ScriptedChatModel(
            [
                tool_response(
                    "bash-confirm-1",
                    "Bash",
                    json.dumps(
                        {
                            "command": command,
                            "description": "Create test directory",
                        },
                    ),
                ),
                text_response("confirmed command finished"),
            ],
        ),
        toolkit=Toolkit(tools=[Bash()]),
    )

    first_events = [
        event
        async for event in agent.reply_stream(UserMsg(name="user", content="run python version"))
    ]
    confirm_event = next(event for event in first_events if isinstance(event, RequireUserConfirmEvent))
    confirm_result = UserConfirmResultEvent(
        reply_id=confirm_event.reply_id,
        confirm_results=[
            ConfirmResult(
                confirmed=True,
                tool_call=confirm_event.tool_calls[0],
                rules=confirm_event.tool_calls[0].suggested_rules,
            ),
        ],
    )

    second_events = [event async for event in agent.reply_stream(confirm_result)]
    context_text = "\n".join(joined_text(msg.content) for msg in agent.state.context)
    result_states = [
        event.state
        for event in second_events
        if getattr(event, "type", None) == "TOOL_RESULT_END"
    ]

    assert ToolResultState.SUCCESS in result_states
    assert target_dir.exists()
    assert "confirmed command finished" in context_text
