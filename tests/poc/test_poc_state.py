from agentscope.message import UserMsg
from agentscope.state import AgentState


def test_agent_state_can_round_trip_json():
    state = AgentState()
    state.summary = "phase 0.5 state persistence poc"
    state.context.append(UserMsg(name="user", content="remember this"))

    restored = AgentState.model_validate_json(state.model_dump_json())

    assert restored.session_id == state.session_id
    assert restored.summary == state.summary
    assert restored.context[0].get_text_content() == "remember this"
