"""Phase 9b 多任务执行和 prior_task_summaries 测试。"""

import pytest

from my_coding_team.orchestration.task_runner import _build_contract_from_item
from my_coding_team.schemas.task import TaskItem
from my_coding_team.schemas.workflow import RepoContext


def test_build_contract_injects_prior_summaries():
    """prior_task_summaries 应注入到 contract 中。"""
    repo = RepoContext(relevant_files=["src/a.py"], test_entrypoints=["tests/"])
    item = TaskItem(task_id="T2", title="Second task", files=["src/b.py"])
    prior = [{"task_id": "T1", "files_changed": ["src/a.py"], "summary": "Added function A"}]

    contract = _build_contract_from_item(item, repo, prior)
    assert contract.task_id == "T2"
    assert len(contract.prior_task_summaries) == 1
    assert contract.prior_task_summaries[0]["task_id"] == "T1"
    assert contract.prior_task_summaries[0]["summary"] == "Added function A"


def test_build_contract_sets_red_for_code():
    """代码任务应设置 test_first_requirement='required'。"""
    repo = RepoContext(relevant_files=["src/main.py"], test_entrypoints=["tests/"])
    item = TaskItem(task_id="T1", title="Code", files=["src/main.py"])
    contract = _build_contract_from_item(item, repo, [])
    assert contract.test_first_requirement == "required"
    assert contract.red_allowed_files == ["tests/**"]


def test_build_contract_skips_red_for_docs():
    """文档任务应设置 test_first_requirement='not_applicable'。"""
    repo = RepoContext(relevant_files=["README.md"])
    item = TaskItem(task_id="T1", title="Docs", files=["README.md"])
    contract = _build_contract_from_item(item, repo, [])
    assert contract.test_first_requirement == "not_applicable"


def test_build_contract_falls_back_to_relevant_files():
    """TaskItem 没有 files 时应 fallback 到 repo context。"""
    repo = RepoContext(relevant_files=["src/x.py"])
    item = TaskItem(task_id="T1", title="No files", files=["default.py"])
    contract = _build_contract_from_item(item, repo, [])
    assert contract.allowed_files == ["default.py"]
