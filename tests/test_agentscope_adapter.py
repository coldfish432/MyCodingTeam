from my_coding_team.runtime import agentscope_adapter as adapter


def test_agentscope_adapter_reexports_runtime_symbols():
    expected = [
        "Agent",
        "AgentState",
        "PermissionContext",
        "PermissionMode",
        "PermissionRule",
        "PermissionBehavior",
        "Toolkit",
        "Bash",
        "Read",
        "Write",
        "Edit",
        "Glob",
        "Grep",
        "LocalWorkspace",
        "DockerWorkspace",
    ]

    for name in expected:
        assert getattr(adapter, name)
