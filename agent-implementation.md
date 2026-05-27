# My Coding Team Agent Implementation (v4)

本文档定义当前代码层面的实现接口、模块职责、schema、权限策略、Agent 工厂和 MVP workflow。施工阶段顺序与 MVP 范围以 `construction-plan.md` 为准；系统定位与流程纪律以 `myCodingTeam.md` 为准。

## 1. 实现边界

本文档回答：

- 项目目录如何组织。
- 哪些模块可以 import AgentScope。
- Pydantic schema 如何定义和校验。
- PermissionRule 如何由 TaskContract 生成。
- 每个 Agent 的输入、输出、工具、权限和调用方式。
- 编排层如何调用 Agent，同时保持 PM Orchestrator 是 Python 状态机。

本文档不回答：

- Phase 0 到 Phase 13 的施工顺序。
- MVP 是否包含 TDD、Full Flow、Review-Only。
- ReviewRoom 是否拆分。

这些统一以 `construction-plan.md` 为准。

## 2. 当前目录结构

```text
my_coding_team/
  __init__.py
  __main__.py
  cli.py
  config.py

  schemas/
    common.py
    workflow.py
    task.py
    review.py
    delivery.py

  runtime/
    agentscope_adapter.py
    factory.py
    llm_client.py
    middleware.py
    mock_model.py
    prompts.py

  orchestration/
    cost_budget.py
    permission_builder.py
    pm_orchestrator.py
    state_machine.py
    task_runner.py
    workspace_manager.py

  agents/
    intake_router.py
    delivery.py
    context_scout.py
    planning.py
    task_implementation.py
    qa_verification.py
    review_room.py

  workflows/
    direct_answer.py
    lightweight.py

  prompts/
    intake_router.md
    context_scout.md
    planning.md
    task_implementation.md
    qa_verification.md
    review_room.md
    delivery.md
    shape.md
    specification.md
    tdd.md
```

测试目录：

```text
tests/
  poc/
  smoke/
  test_agentscope_adapter.py
  test_architecture_boundaries.py
  test_cli.py
  test_package.py
  test_permission_builder.py
  test_phase4_5_orchestrator.py
  test_phase6_workspace_context.py
  test_phase7_lightweight.py
  test_runtime_phase3.py
  test_schemas.py
```

## 3. AgentScope 适配层

`runtime/agentscope_adapter.py` 是项目中唯一允许直接 import `agentscope.*` 的模块。业务层、Agent facade、orchestration、workflow 都必须通过该适配层使用 AgentScope 符号。

当前适配层 re-export：

- `Agent`
- `AgentState`
- `PermissionContext`
- `PermissionMode`
- `PermissionRule`
- `PermissionBehavior`
- `Toolkit`
- `Bash`
- `Read`
- `Write`
- `Edit`
- `Glob`
- `Grep`
- `LocalWorkspace`
- `DockerWorkspace`
- `ChatModelBase`
- `ChatResponse`
- `CredentialBase`
- `TextBlock`
- `ToolCallBlock`
- `UserMsg`

硬规则：

- 除 `runtime/agentscope_adapter.py` 外，不直接 import `agentscope.*`。
- 不使用 v1 `ReActAgent`。
- 不使用 `PermissionMode.BYPASS`。
- AgentScope v2 API 变化时，只改 adapter 和 runtime 层。

架构边界由 `tests/test_architecture_boundaries.py` 锁定。

## 4. Schema

所有项目 schema 都继承 `StrictBaseModel`：

- `extra="forbid"`，禁止模型输出携带未知字段。
- `validate_assignment=True`，赋值时继续校验。

### 4.1 common.py

- `Confidence`: `0.0 <= value <= 1.0`。
- `OutputStatus`: `success | needs_clarification | blocked | failed`。
- `RiskLevel`: `low | medium | high`。
- `WorkflowKind`: `direct_answer | review_only | lightweight | full`。
- `Evidence`: 文件、行号、摘录和说明。
- `AgentOutput`: 通用 Agent 输出外壳。

### 4.2 workflow.py

- `RouteDecision`: Intake Router 的结构化路由结果。
- `ProblemFrame`: Phase 9a Shape 占位 schema。
- `ProductBrief`: Phase 9a Specification 占位 schema。
- `DesignSignoff`: Full Flow 设计确认结果。
- `WorkspaceRecord`: 工作区 Git 状态快照。
- `RepoContext`: Context Scout 产出的仓库事实摘要。
- `TeamState`: PM Orchestrator 推进流程时使用的共享状态。

关键校验：

- `workflow` 只能是四种工作流之一。
- `risk` 只能是三种风险级别之一。
- `llm_calls_used <= llm_calls_budget`。

### 4.3 task.py

- `TaskItem`: 任务队列条目。
- `TaskQueue`: 后续多任务队列，MVP 只使用单任务。
- `TaskContract`: 实现和验证共同遵守的任务合同。
- `TaskRepairContract`: repair loop 使用的修复合同。
- `RedResult`: Phase 8 TDD RED 占位 schema。
- `ImplementationResult`: 实现阶段输出。
- `VerificationResult`: 验证阶段输出。
- `TaskRunResult`: 单任务完整运行结果。

关键校验：

- `TaskContract.allowed_files` 不能为空。
- `TaskRepairContract.allowed_files` 不能为空。

### 4.4 review.py

- `ReviewFinding`: 单条审查发现。
- `TaskReviewResult`: 单任务审查结果。
- `FinalReviewReport`: DeliveryPackage 使用的最终审查报告。

关键校验：

- `must_fix` 非空时，`approval` 必须为 `false`。
- `must_fix` 非空时，必须提供 `evidence`。
- 有未解决 `must_fix` 时，`TaskReviewResult` 和 `FinalReviewReport` 不允许 approval。

### 4.5 delivery.py

- `FinishDecision`: 交付裁决，状态为 `success | blocked | failed`。
- `DeliveryPackage`: CLI 和用户看到的最终交付包。

`DeliveryPackage` 必须说明：

- 原始请求。
- 成功、阻断或失败原因。
- 修改文件。
- 验证结果。
- Review 结果。
- 剩余风险。
- LLM 调用数。

## 5. Runtime

### 5.1 prompts.py

`load_prompt(name)` 从 `my_coding_team/prompts/{name}.md` 加载 prompt。文件不存在时抛 `PromptNotFoundError`。

### 5.2 mock_model.py

提供两类测试模型：

- `ScriptedChatModel`: AgentScope v2 POC 使用，按顺序返回 `ChatResponse`。
- `DeterministicModel`: MVP 单元测试使用，提供 `complete_text()` 和 `complete_json()`。

### 5.3 llm_client.py

`OpenAICompatibleModel` 使用标准库 `urllib` 调用 OpenAI-compatible `/chat/completions`。

配置来源：

- `LLM_MODEL`
- `LLM_BASE_URL`
- `LLM_API_KEY`

也兼容：

- `MY_CODING_TEAM_MODEL_NAME`
- `MY_CODING_TEAM_MODEL_BASE_URL`
- `MY_CODING_TEAM_API_KEY`

安全规则：

- API key 只读取，不打印。
- `.env` 不进入 Git。
- `MVP_STATUS.md` 只记录 key 是否配置。

### 5.4 middleware.py

当前提供轻量 helper：

- `parse_schema(schema_class, payload)`: 将 JSON 字符串或 dict 解析为 Pydantic schema。
- `RuntimeLog`: 内存事件记录。
- `CostBudget`: 简单预算计数器。
- `dumps_for_prompt(value)`: 将 schema/dict 格式化为 JSON 文本。

MVP 没有依赖 AgentScope middleware hook；schema parse、日志和预算先由调用包装函数保证可测。

### 5.5 factory.py

`create_agent(...)` 统一创建 AgentScope `Agent`，注入：

- `Toolkit`
- `PermissionContext`
- `permission_mode`
- `allow_rules`
- `deny_rules`
- `working_directories`

## 6. Permission Builder

`orchestration/permission_builder.py` 负责把业务合同转换为 AgentScope 权限规则。

### 6.1 只读 probe allow/deny

Phase 0.5 POC 发现：

- AgentScope 2.0.0 的 `PermissionMode.EXPLORE` 会在工具层拒绝 `Bash`，即使命令是 `pwd`、`ls`、`git status` 等只读命令。
- AgentScope v2 内置安全层对 `rm -rf` 等 destructive 命令会发出 `RequireUserConfirmEvent`；只靠“不在 allow_rules 中”不足以变成硬拒绝。

因此，需要 Bash 探查的只读 Agent 必须使用：

```python
permission_mode = PermissionMode.DONT_ASK
allow_rules = build_readonly_probe_rules()
deny_rules = build_readonly_probe_deny_rules()
```

`READONLY_BASH_PREFIXES` 包含：

- `git status:*`
- `git log:*`
- `git diff:*`
- `git show:*`
- `git branch:*`
- `git rev-parse:*`
- `ls:*`
- `cat:*`
- `head:*`
- `tail:*`
- `wc:*`
- `find:*`
- `rg:*`
- `tree:*`
- `pwd:*`
- `file:*`

`DESTRUCTIVE_BASH_PREFIXES` 包含：

- `rm:*`
- `rmdir:*`
- `mv:*`
- `dd:*`
- `shred:*`
- `chmod:*`
- `chown:*`
- `git checkout:*`
- `git reset:*`
- `git clean:*`
- `git rebase:*`
- `git push:*`
- `git merge:*`
- `git commit:*`
- `git branch -D:*`
- `sudo:*`
- `curl:*`
- `wget:*`

### 6.2 TaskContract allow rules

`build_task_allow_rules(contract)` 生成：

- `Read: **`
- `Grep: **`
- `Glob: **`
- `Write`: `contract.allowed_files`
- `Edit`: `contract.allowed_files`
- `Bash`: 由 `contract.verification_commands` 转换出的命令前缀。

安全校验：

- `allowed_files` 必须是仓库相对路径。
- 禁止绝对路径。
- 禁止 `..` 父级穿越。
- 禁止 home 目录目标。
- 重复规则会去重。

`to_bash_prefix(command)` 示例：

- `pytest tests/test_x.py -> pytest:*`
- `npm run build -> npm run:*`
- `git status --short -> git status:*`
- `python -m pytest -> python -m:*`
- 空命令返回 `None`。

## 7. Agent Facade

### 7.1 Intake Router

模块：`agents/intake_router.py`

职责：

- 将用户请求路由到 `direct_answer`、`review_only`、`lightweight` 或 `full`。
- MVP 默认使用确定性规则。
- 如果传入模型，则调用模型生成 `RouteDecision`。

路由规则：

- 解释、总结、是什么：`direct_answer`
- review、检查、审查、PR：`review_only`
- 改、修、增加、删除、新增、实现、fix、add、update：`lightweight`
- 架构、系统、完整流程、cross-module、full：`full`
- 空请求：`needs_clarification=true`

### 7.2 Context Scout

模块：`agents/context_scout.py`

职责：

- 收集仓库中的 Python、Markdown、TOML 文件。
- 提取测试入口。
- 推断基础验证命令。
- 记录 dirty workspace 风险。
- 输出 `RepoContext`。

Agent 工厂必须使用：

```python
DONT_ASK + build_readonly_probe_rules() + build_readonly_probe_deny_rules()
```

### 7.3 Planning

模块：`agents/planning.py`

职责：

- Phase 7 只生成单个 `TaskContract`。
- `allowed_files` 必须非空。
- `verification_commands` 必须非空。
- 没有模型时使用 fallback contract。

fallback 策略：

- 优先选择相关 Markdown 文件。
- 否则选择第一个相关文件。
- 如果存在测试入口，验证命令为 `python -m pytest`。
- 否则验证命令为 `python -m my_coding_team doctor`。

### 7.4 Task Implementation

模块：`agents/task_implementation.py`

职责：

- 根据 `TaskContract` 应用模型输出的文件替换。
- 只能修改 `allowed_files`。
- 禁止空路径、绝对路径、父级穿越路径。
- 输出 `ImplementationResult`。

模型输出格式：

```json
{
  "summary": "what changed",
  "changes": [
    {"path": "README.md", "content": "complete replacement content"}
  ]
}
```

当前 MVP 使用完整文件替换，不做 patch merge。

### 7.5 QA Verification

模块：`agents/qa_verification.py`

职责：

- 只运行 `TaskContract.verification_commands`。
- 记录 stdout/stderr 摘要和失败命令。
- 失败时 `passed=false`。
- 不安全命令标记为 not_run/failed，不执行。

MVP 安全命令前缀：

- `pytest`
- `python -m pytest`
- `py -m pytest`
- `python -m my_coding_team doctor`

### 7.6 ReviewRoom

模块：`agents/review_room.py`

职责：

- 合并版 reviewer。
- 验证失败时必须阻断 approval。
- 明显越界修改时必须阻断 approval。
- must_fix 必须带 evidence。

MVP 暂不做多 reviewer 拆分。

### 7.7 Delivery

模块：`agents/delivery.py`

职责：

- 构建 `DeliveryPackage`。
- 统一成功、阻断和失败输出。
- 不隐藏验证失败、review 阻断和权限拒绝。

## 8. Orchestration

### 8.1 PM Orchestrator

模块：`orchestration/pm_orchestrator.py`

`run_request(request, budget=10, workspace=None, mode="auto", model=None)` 是主入口。

流程：

1. 创建 `TeamState`。
2. 如果 `mode=auto`，调用 Intake Router。
3. `direct_answer` 进入 Direct Answer workflow。
4. `lightweight` 进入 Lightweight workflow。
5. `review_only` 和 `full` 在 MVP 中返回 blocked。
6. budget 超限时返回 blocked delivery。

PM Orchestrator 是 Python 状态机，不是 LLM Agent。

### 8.2 State Machine

模块：`orchestration/state_machine.py`

`transition(current, target)` 校验状态转换是否合法。

合法状态：

- `initialized`
- `routed`
- `direct_answer`
- `workspace_prepared`
- `context_collected`
- `planned`
- `implemented`
- `verified`
- `reviewed`
- `delivered`
- `blocked`

### 8.3 Workspace Manager

模块：`orchestration/workspace_manager.py`

职责：

- 检查是否 Git 仓库。
- 记录当前 commit。
- 记录 `git status --short`。
- 提取 dirty files。
- 非 Git 目录降级为 `is_git=false`。
- 提供 `local_workspace()` async context manager。

硬规则：

- 不执行 reset、merge、clean、delete worktree。
- 不丢弃用户改动。

### 8.4 Task Runner

模块：`orchestration/task_runner.py`

`run_single_task(contract, workspace_root, implementation_model=None, repair_model=None, max_repairs=2)` 执行：

1. Task Implementation。
2. QA Verification。
3. ReviewRoom。
4. 如果 review approval 通过，返回成功。
5. 如果有 must_fix，最多 repair 2 次。
6. 超过 repair 上限，返回 `blocked_by_repair_limit`。
7. 如果实现阶段发生 `PermissionError`，返回 `blocked_by_permission_denied`。

权限错误是安全阻断，不让 CLI 崩溃，也不继续执行验证命令。

## 9. Workflows

### 9.1 Direct Answer

模块：`workflows/direct_answer.py`

职责：

- 不读取仓库。
- 不写文件。
- 使用模型回答纯问答请求。
- 返回 `DeliveryPackage`。

### 9.2 Lightweight

模块：`workflows/lightweight.py`

流程：

1. `inspect_git_workspace`
2. `call_context_scout`
3. `call_planning_for_single_contract`
4. `run_single_task`
5. `build_delivery_package`

交付规则：

- verification failed 不能成功交付。
- review must_fix 不能成功交付。
- permission denied 不能成功交付。
- changed_files 来自 `ImplementationResult`。
- risks 来自 `RepoContext`。

## 10. CLI

模块：`cli.py`

子命令：

```text
python -m my_coding_team doctor
python -m my_coding_team config
python -m my_coding_team run "request" --budget N --workspace PATH --mode auto|direct|lightweight
```

`run` 默认使用 `.env` 中的真实 LLM。

可用 `--mock` 强制使用本地确定性模型：

```text
python -m my_coding_team run "解释一下 schema" --mode direct --mock
```

## 11. Prompt 模板

当前 prompt 文件：

- `intake_router.md`
- `context_scout.md`
- `planning.md`
- `task_implementation.md`
- `qa_verification.md`
- `review_room.md`
- `delivery.md`
- `shape.md`
- `specification.md`
- `tdd.md`

MVP 中 `shape.md`、`specification.md`、`tdd.md` 只是占位，分别属于 Phase 9a 和 Phase 8。

prompt 必须说明：

- 角色职责。
- 输入。
- 输出 JSON schema。
- 不可违反的硬规则。
- evidence 要求。
- stop/block 条件。

## 12. 测试

当前测试覆盖：

- AgentScope v2 POC。
- schema 校验和序列化。
- adapter import 边界。
- permission builder。
- prompt loader。
- mock model。
- budget helper。
- intake route。
- PM Orchestrator direct/blocked。
- Workspace Manager。
- Context Scout。
- Planning。
- Task Implementation 权限拒绝。
- QA Verification。
- ReviewRoom。
- Lightweight workflow。
- repair loop。

当前基线：

```text
python -m pytest
65 passed
```

真实 LLM smoke：

- Direct Answer smoke：通过。
- Lightweight positive smoke：通过。
- Negative permission smoke：通过，越权写被 `blocked_by_permission_denied` 阻断，目标文件未创建。
- Negative verification smoke：通过，验证失败不会成功交付，最终 blocked。

## 13. 工程硬约束

- PM Orchestrator 是 Python 状态机，不是 LLM Agent。
- Agent 不直接修改 `TeamState`。
- 所有 AgentScope import 必须集中在 adapter。
- Reviewer 不写代码。
- Task Implementation 只能写 `allowed_files`。
- QA 只能运行合同授权的验证命令。
- Workspace Manager 不丢弃用户改动。
- Branch Finisher 不执行 destructive 操作。
- Schema parse 失败不能静默吞掉。
- Repair loop 默认最多 2 次。
- Must Fix 必须有 evidence。
- 未运行验证必须写明 not_run 原因。
- Delivery 不能隐藏失败、跳过、blocked 或 partial 状态。
- 只读 Agent 不使用 `EXPLORE + Bash`。
- 需要 Bash 的只读 Agent 必须使用 `DONT_ASK + build_readonly_probe_rules() + build_readonly_probe_deny_rules()`。

## 14. Phase 8 前状态

MVP 已完成 Phase 0 到 Phase 7。进入 Phase 8 前已经补充两个真实 LLM 负向 smoke：

- 权限层负向 smoke：真实 LLM 路径下强制输出越权写，workflow 返回 `blocked_by_permission_denied`。
- 验证失败负向 smoke：真实 LLM 路径下强制验证失败，workflow 不交付成功。

Phase 8 可以在现有 `TaskContract`、`RedResult`、`TaskRunner` 基础上加入 TDD RED-GREEN-REFACTOR。
