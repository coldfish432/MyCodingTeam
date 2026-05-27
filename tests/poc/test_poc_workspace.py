from pathlib import Path

from agentscope.workspace import LocalWorkspace


async def test_local_workspace_initialize_and_close(tmp_path: Path):
    workspace = LocalWorkspace(workdir=str(tmp_path / "workspace"))

    await workspace.initialize()
    instructions = await workspace.get_instructions()

    assert workspace.is_alive
    assert Path(workspace.workdir).is_absolute()
    assert (Path(workspace.workdir) / "skills").exists()
    assert (Path(workspace.workdir) / ".mcp").exists()
    assert "workspace" in instructions.lower()

    await workspace.close()
    assert not workspace.is_alive
