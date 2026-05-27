from pathlib import Path


def test_business_code_imports_agentscope_only_through_adapter():
    package_root = Path("my_coding_team")
    adapter_path = package_root / "runtime" / "agentscope_adapter.py"
    offenders = []

    for path in package_root.rglob("*.py"):
        if path == adapter_path:
            continue
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith(("import agentscope", "from agentscope")):
                offenders.append(f"{path}:{line_number}: {stripped}")

    assert offenders == []
