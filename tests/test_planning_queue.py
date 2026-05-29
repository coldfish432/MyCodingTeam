"""Phase 9b TaskQueue planning 和多任务执行测试。"""

import pytest

from my_coding_team.agents.planning import _fallback_queue
from my_coding_team.core.registry import STEPS
from my_coding_team.core.step import StepContext
from my_coding_team.schemas.step_inputs import PlanningQueueInput
from my_coding_team.schemas.task import TaskItem, TaskQueue
from my_coding_team.schemas.workflow import ProductBrief, RepoContext


@pytest.mark.asyncio
async def test_planning_queue_fallback():
    """没有模型时应返回最小 TaskQueue。"""
    brief = ProductBrief(
        title="Test Queue",
        summary="Testing queue generation.",
        goals=["Goal 1"],
        non_goals=["Not X", "Not Y"],
        acceptance_criteria=["pytest passes"],
    )
    repo = RepoContext(relevant_files=["src/main.py"])
    queue = _fallback_queue(brief, repo)
    assert isinstance(queue, TaskQueue)
    assert len(queue.items) == 1
    assert queue.items[0].task_id == "T1"
    assert queue.items[0].files == ["src/main.py"]


@pytest.mark.asyncio
async def test_planning_queue_with_mock_model():
    """mock 模型应返回合法 TaskQueue。"""
    from my_coding_team.runtime.mock_model import DeterministicModel

    brief = ProductBrief(
        title="Multi Task",
        summary="Multi-task test.",
        goals=["G1"],
        non_goals=["N1", "N2"],
        acceptance_criteria=["pytest"],
    )
    repo = RepoContext(relevant_files=["src/a.py", "src/b.py"])

    model = DeterministicModel(json_outputs=[{
        "items": [
            {"task_id": "T1", "title": "Add function A", "description": "Implement A", "files": ["src/a.py"], "depends_on": [], "risk": "low"},
            {"task_id": "T2", "title": "Add function B", "description": "Implement B", "files": ["src/b.py"], "depends_on": ["T1"], "risk": "low"},
        ],
        "strategy": "sequential",
        "estimated_total_calls": 10,
    }])

    queue = await STEPS["planning_queue"].run(
        PlanningQueueInput(brief=brief.model_dump(), repo_context=repo.model_dump()),
        StepContext(model=model),
    )
    assert len(queue.items) == 2
    assert queue.items[0].task_id == "T1"
    assert queue.items[1].task_id == "T2"
    assert queue.items[1].depends_on == ["T1"]


def test_task_queue_rejects_too_few_items():
    """TaskQueue 必须至少有 1 个 item。"""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        TaskQueue(items=[])


def test_task_queue_rejects_too_many_items():
    """TaskQueue 最多 15 个 items。"""
    from pydantic import ValidationError
    items = [TaskItem(task_id=f"T{i}", title=f"T{i}", files=["src/a.py"]) for i in range(20)]
    with pytest.raises(ValidationError):
        TaskQueue(items=items)


def test_task_queue_rejects_duplicate_ids():
    """TaskQueue 不允许重复 task_id。"""
    from pydantic import ValidationError
    items = [
        TaskItem(task_id="T1", title="One", files=["src/a.py"]),
        TaskItem(task_id="T1", title="Two", files=["src/b.py"]),
    ]
    with pytest.raises(ValidationError) as exc_info:
        TaskQueue(items=items)
    assert "unique" in str(exc_info.value).lower()


def test_task_item_rejects_too_many_files():
    """TaskItem.files 不能超过 8 个。"""
    from pydantic import ValidationError
    item = TaskItem(task_id="T1", title="X", files=[f"src/f{i}.py" for i in range(10)])
    with pytest.raises(ValidationError) as exc_info:
        TaskQueue(items=[item])
    assert "1-8" in str(exc_info.value)


def test_task_item_rejects_empty_files():
    """TaskItem.files 不能为空。"""
    from pydantic import ValidationError
    item = TaskItem(task_id="T1", title="X", files=[])
    with pytest.raises(ValidationError) as exc_info:
        TaskQueue(items=[item])
    assert "1-8" in str(exc_info.value)


def test_task_queue_accepts_valid_items():
    """合法 TaskQueue 应该验证通过。"""
    items = [
        TaskItem(task_id="T1", title="Task 1", files=["src/a.py"]),
        TaskItem(task_id="T2", title="Task 2", files=["src/b.py", "src/c.py"], depends_on=["T1"]),
    ]
    queue = TaskQueue(items=items, strategy="sequential", estimated_total_calls=10)
    assert len(queue.items) == 2
