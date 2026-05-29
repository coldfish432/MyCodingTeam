import pytest

from my_coding_team.orchestration.permission_builder import (
    build_readonly_probe_deny_rules,
    build_readonly_probe_rules,
    build_task_allow_rules,
    to_bash_prefix,
)
from my_coding_team.schemas.task import TaskContract, TaskRepairContract


def _contents(rules, tool_name):
    return [rule.rule_content for rule in rules.get(tool_name, [])]


def test_readonly_probe_rules_include_allow_and_deny_layers():
    allow_rules = build_readonly_probe_rules()
    deny_rules = build_readonly_probe_deny_rules()

    assert "git status:*" in _contents(allow_rules, "Bash")
    assert "Read" in allow_rules
    assert "rm:*" in _contents(deny_rules, "Bash")
    assert "git checkout:*" in _contents(deny_rules, "Bash")


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("pytest tests/test_x.py", "pytest:*"),
        ("npm run build", "npm run:*"),
        ("pnpm test", "pnpm test:*"),
        ("git status --short", "git status:*"),
        ("python -m pytest tests", "python -m:*"),
        ("", None),
        ("   ", None),
    ],
)
def test_to_bash_prefix(command, expected):
    assert to_bash_prefix(command) == expected


def test_build_task_allow_rules_maps_contract_to_file_and_bash_rules():
    contract = TaskContract(
        task_id="T1",
        goal="Edit docs",
        allowed_files=["README.md", "docs/"],
        verification_commands=["pytest tests/test_docs.py", "npm run build"],
    )

    rules = build_task_allow_rules(contract)

    assert _contents(rules, "Write") == ["README.md", "docs/**"]
    assert _contents(rules, "Edit") == ["README.md", "docs/**"]
    assert _contents(rules, "Bash") == ["pytest:*", "npm run:*"]
    assert _contents(rules, "Read") == ["**"]


def test_build_task_allow_rules_deduplicates_repeated_rules():
    contract = TaskContract(
        task_id="T1",
        goal="Edit docs",
        allowed_files=["README.md", "README.md"],
        verification_commands=["pytest tests/a.py", "pytest tests/b.py"],
    )

    rules = build_task_allow_rules(contract)

    assert _contents(rules, "Write") == ["README.md"]
    assert _contents(rules, "Edit") == ["README.md"]
    assert _contents(rules, "Bash") == ["pytest:*"]


@pytest.mark.parametrize(
    "bad_path",
    [
        "../outside.py",
        "src/../../outside.py",
        "/tmp/outside.py",
        "C:/Users/yuan/outside.py",
        "",
        "~/.ssh/config",
    ],
)
def test_build_task_allow_rules_rejects_dangerous_paths(bad_path):
    contract = TaskContract(
        task_id="T1",
        goal="Edit file",
        allowed_files=[bad_path],
    )

    with pytest.raises(ValueError):
        build_task_allow_rules(contract)


def test_empty_verification_commands_do_not_create_bash_rules():
    contract = TaskContract(
        task_id="T1",
        goal="Edit file",
        allowed_files=["README.md"],
        verification_commands=[""],
    )

    rules = build_task_allow_rules(contract)

    assert "Bash" not in rules


def test_repair_contract_extends_permissions_to_red_files_only_when_requested():
    contract = TaskRepairContract(
        original_task_id="T1",
        reason="Fix RED test quality before delivery.",
        allowed_files=["utils/calc.py"],
        red_allowed_files=["tests/test_calc.py"],
        extend_allowed_files_to_red=True,
    )

    rules = build_task_allow_rules(contract)

    assert _contents(rules, "Write") == ["utils/calc.py", "tests/test_calc.py"]


def test_repair_contract_keeps_red_files_out_without_extension_flag():
    contract = TaskRepairContract(
        original_task_id="T1",
        reason="Fix production bug.",
        allowed_files=["utils/calc.py"],
        red_allowed_files=["tests/test_calc.py"],
        extend_allowed_files_to_red=False,
    )

    rules = build_task_allow_rules(contract)

    assert _contents(rules, "Write") == ["utils/calc.py"]
