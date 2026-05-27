from pathlib import Path

from agentscope.agent import Agent
from agentscope.message import ToolResultState, UserMsg
from agentscope.permission import PermissionBehavior, PermissionContext, PermissionMode, PermissionRule
from agentscope.state import AgentState
from agentscope.tool import Toolkit, Write

from .helpers import ScriptedChatModel, text_response, tool_response


async def test_permission_rule_blocks_out_of_scope_write(tmp_path: Path):
    target = tmp_path / "src" / "foo.py"
    agent = Agent(
        name="PocPermissionAgent",
        system_prompt="Try the requested write.",
        model=ScriptedChatModel(
            [
                tool_response(
                    "write-1",
                    "Write",
                    f'{{"file_path": "{target.as_posix()}", "content": "blocked"}}',
                ),
                text_response("write attempted"),
            ],
        ),
        toolkit=Toolkit(tools=[Write()]),
        state=AgentState(
            permission_context=PermissionContext(
                mode=PermissionMode.DONT_ASK,
                allow_rules={
                    "Write": [
                        PermissionRule(
                            tool_name="Write",
                            rule_content=str((tmp_path / "tests" / "**").as_posix()),
                            behavior=PermissionBehavior.ALLOW,
                            source="poc",
                        ),
                    ],
                },
            ),
        ),
    )

    await agent.reply(UserMsg(name="user", content="write outside tests"))
    tool_results = [
        block
        for msg in agent.state.context
        for block in msg.get_content_blocks("tool_result")
    ]

    assert not target.exists()
    assert any(block.state == ToolResultState.DENIED for block in tool_results)
