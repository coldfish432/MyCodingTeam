# My Coding Team Construction Plan (v3, Canonical)

> **本文档是唯一施工顺序准则。**  
> `myCodingTeam.md` 只描述系统目标、架构边界、流程纪律和角色分工；`agent-implementation.md` 只描述模块接口、schema、权限和 Agent 工厂实现。任何阶段边界、验收标准、MVP 范围、延期范围，都以本文档为准。

## 0. 文档边界和冲突解决规则

三份文档的职责如下：

| 文件 | 职责 | 不再承担 |
|---|---|---|
| `construction-plan.md` | 施工阶段、落地顺序、每阶段产物、验收标准、预算、升级路径 | 具体 Agent 代码细节 |
| `myCodingTeam.md` | 系统愿景、架构原则、流程纪律、Agent 角色地图、运行时边界 | 详细施工计划、每阶段任务清单 |
| `agent-implementation.md` | 目录结构、schema、适配层、权限策略、Agent 工厂、每个 Agent 的输入输出和调用方式 | 产品定位、完整施工路线图 |

冲突解决规则：

1. **阶段顺序以本文档为准。** 任何文件出现“第一阶段全部实现 Full Flow / TDD / Review-Only”的说法，都视为旧口径。
2. **MVP = Phase 0 到 Phase 7，且必须包含 Phase 0.5 POC。** MVP 不包含 TDD、Full Product Flow、多任务队列、Review-Only Flow、专项 Agent、Docker 工程化。
3. **TDD 从 Phase 8 开始。** Phase 7 的 Lightweight Build Loop 先做“实现 → 验证 → Review → Delivery”的最小闭环。
4. **Full Product Flow 从 Phase 9a/9b/9c 逐步完成。** Shape/Spec/Signoff、TaskQueue、多任务执行、Final Verification/Review 分开交付。
5. **ReviewRoom 第一版保持合并。** 拆分 reviewer 只能在 Phase 13 且满足实证触发条件后进行。
6. **权限层使用 AgentScope v2 内置工具 + `PermissionContext`。** 不自造 `RestrictedTool`，除非 Phase 0.5 POC 证明 v2 权限无法满足需求。
7. **PM Orchestrator 永远是 Python 状态机，不是 LLM Agent。**

## 1. 总体施工原则

- 先验证 AgentScope v2 真实能力，再铺开架构。Phase 0.5 是硬门，不能跳过。
- 先做可运行骨架，再做智能能力。
- 先做 schema、状态模型、权限策略，再接真实 Agent。
- `orchestration/` 从第一天就是确定性 Python 状态机；`agents/` 才是 AgentScope v2 `Agent` 工厂。
- 先完成 Lightweight Flow，再扩展 Full Product Flow。
- 先用 mock model 和 deterministic fixture 验证流程，再接真实模型。
- 每阶段都有可运行验收，不用“后面补”替代完成标准。
- 每阶段都记录 LLM 调用预算，避免原型在真实使用中成本失控。

## 2. 阶段总览

```text
Phase 0    -> 项目骨架和技术基线
Phase 0.5  -> AgentScope v2 POC（硬门，不可跳过）
Phase 1    -> Schema 和状态模型
Phase 2    -> 权限策略层和 AgentScope 适配器
Phase 3    -> Agent 工厂、Prompt 系统、Middleware、Mock Model
Phase 4    -> Intake Router 和 Direct Answer Flow
Phase 5    -> PM Orchestrator 最小闭环
Phase 6    -> Context Scout 和 Workspace Manager
Phase 7    -> Task Contract 和 Lightweight Build Loop（MVP）
Phase 8    -> TDD RED-GREEN-REFACTOR
Phase 9a   -> Shape + Specification + Design Signoff
Phase 9b   -> TaskQueue + 多任务 TaskRunner
Phase 9c   -> Final Verification + Final Review + Global Repair Loop
Phase 10   -> Review-Only Flow
Phase 11   -> 专项 Agent 扩展（Debug / Browser / Documentation）
Phase 12   -> 工程化和交付能力
Phase 13   -> ReviewRoom 拆分评估（实证触发）
```

里程碑定义：

| 里程碑 | 包含阶段 | 能力范围 |
|---|---:|---|
| 骨架可运行 | Phase 0 | package、CLI、doctor、测试框架 |
| 技术可行 | Phase 0.5 | v2 Agent、权限、HITL、状态、Workspace POC 通过 |
| 框架可测 | Phase 1-3 | schema、适配器、权限规则、mock agent、middleware |
| 问答可用 | Phase 4-5 | Direct Answer + PM 状态机 |
| 仓库感知 | Phase 6 | Context Scout + Workspace Record |
| **MVP** | **Phase 0-7** | 小任务安全修改闭环 |
| TDD 可用 | Phase 8 | RED 确定性校验 + GREEN + Review |
| Full Flow 可用 | Phase 9a-9c | 复杂需求从规格到最终验证闭环 |
| 日常可用 | Phase 10-12 | Review-only、专项 Agent、持久化、交付包 |
| 高级审查 | Phase 13 | 多 reviewer 拆分，仅在实证需要时做 |

## Phase 0: 项目骨架和技术基线

### 目标

建立一个可以安装、测试、运行的 Python 项目骨架。此阶段不实现复杂 Agent，只确认项目可以稳定启动。

### 要实现

- Python package 结构。
- `pyproject.toml`。
- Python 版本下限 3.11。
- `agentscope>=2.0`、`pydantic>=2.0`、`pytest`、`pytest-asyncio`。
- 基础 CLI：`python -m my_coding_team --help`、`python -m my_coding_team doctor`。
- `config.py` 读取模型配置、日志目录、workspace 默认值，不硬编码 secret。
- 基础测试：package import、CLI help、doctor、AgentScope 版本检查。

### 推荐目录

```text
my_coding_team/
  __init__.py
  __main__.py
  cli.py
  config.py
  runtime/
  schemas/
  orchestration/
  agents/
  workflows/
  prompts/
tests/
```

### 验收标准

- `python -m my_coding_team --help` 正常输出。
- `python -m my_coding_team doctor` 正常输出。
- `pytest` 通过。
- 没有真实模型配置时，doctor 和单测仍可运行。
- AgentScope 版本低于 2.0 时 doctor 明确报错。

### LLM 调用预算

0 次。

### 不做

不写 Agent 编排、不接真实模型、不写文件编辑能力、不做 TDD、Review 或 Full Flow。

## Phase 0.5: AgentScope v2 POC（硬门）

### 目标

在大规模实现前，用 30-80 行级别的 POC 验证 AgentScope v2 是否真的满足架构假设。

### 必跑 POC

1. **单 Agent + Bash + EXPLORE 权限**  
   验证 `Agent.reply()` 能调用 `Bash()`，`ls`、`pwd` 等只读命令能自动放行。

2. **PermissionRule glob 阻止越界写**  
   配置 `Write/Edit` 只允许 `tests/**`，让 Agent 尝试写 `src/foo.py`，确认文件不会被创建。

3. **HITL 用户确认机制**  
   用 `reply_stream()` 捕获 `RequireUserConfirmEvent`，构造 `UserConfirmResultEvent` 后恢复执行。

4. **AgentState 持久化和恢复**  
   `AgentState.model_dump_json()` 后再 `model_validate_json()`，确认上下文可以恢复。

5. **LocalWorkspace + offloader**  
   初始化 `LocalWorkspace`，确认工具列表、工作目录、关闭生命周期可用。

### 产物

- `tests/poc/test_poc_agent_basics.py`
- `tests/poc/test_poc_permissions.py`
- `tests/poc/test_poc_hitl.py`
- `tests/poc/test_poc_state.py`
- `tests/poc/test_poc_workspace.py`
- `POC_RESULTS.md`

### 验收标准

- 5 个 POC 全部通过。
- POC 失败必须在 `POC_RESULTS.md` 写明原因、影响范围和替代方案。
- 如果 v2 API 与假设不符，先更新 `agent-implementation.md`，再进入 Phase 1。

### LLM 调用预算

5-15 次。尽量使用便宜模型。

### 风险应对

- POC-2 失败：考虑自定义 `ToolBase.check_permissions` 作为硬约束补丁。
- POC-3 失败：Design Signoff 改为编排层外部确认，不依赖 v2 event。
- POC-4 失败：短期只持久化 `TeamState`，AgentState 先内存化。
- POC-5 失败：先只用 `LocalWorkspace` 最小能力，不依赖 offloader。
- 多项 POC 失败：暂停 AgentScope 路线，评估 LangGraph 或自写 ReAct loop。

## Phase 1: Schema 和状态模型

### 目标

先把跨 Agent 流转的数据结构固定下来，防止自由文本把流程推乱。

### 要实现

- `schemas/common.py`：`AgentOutput`、`Evidence`、状态枚举、confidence 校验。
- `schemas/workflow.py`：`TeamState`、`RouteDecision`、`ProblemFrame`、`ProductBrief`、`DesignSignoff`、`WorkspaceRecord`。
- `schemas/task.py`：`TaskItem`、`TaskQueue`、`TaskContract`、`TaskRepairContract`、`RedResult`、`ImplementationResult`、`VerificationResult`。
- `schemas/review.py`：`ReviewFinding`、`TaskReviewResult`、`FinalReviewReport`。
- `schemas/delivery.py`：`FinishDecision`、`DeliveryPackage`。

### 校验规则

- workflow 只能是 `direct_answer`、`review_only`、`lightweight`、`full`。
- risk 只能是 `low`、`medium`、`high`。
- confidence 范围为 0.0 到 1.0。
- `TaskContract.allowed_files` 不能为空。
- `ReviewFinding.must_fix` 非空时 `approval=false`。
- `must_fix` 必须有 evidence。
- `TeamState.llm_calls_used <= TeamState.llm_calls_budget`。

### 验收标准

- schema 单测通过。
- 样例 `TeamState` 可以 serialize / deserialize。
- 非法输入报错可定位到字段。

### LLM 调用预算

0 次。

## Phase 2: 权限策略层和 AgentScope 适配器

### 目标

实现业务权限到 AgentScope v2 权限规则的转换。这里不自造 `RestrictedTool`。

### 要实现

- `runtime/agentscope_adapter.py`：项目中唯一直接 import `agentscope.*` 的模块。
- 适配器 re-export：`Agent`、`AgentState`、`PermissionContext`、`PermissionMode`、`PermissionRule`、`PermissionBehavior`、`Toolkit`、`Bash`、`Read`、`Write`、`Edit`、`Glob`、`Grep`、`LocalWorkspace`、`DockerWorkspace`。
- `orchestration/permission_builder.py`：`TaskContract -> allow_rules`。
- `to_bash_prefix(command)`：如 `pytest tests/test_x.py -> pytest:*`，`npm run build -> npm run:*`。

### 验收标准

- 单测覆盖 glob、命令前缀、空命令、危险路径、重复规则。
- 集成测试证明未授权写入会被 v2 权限层拒绝。
- 除 `runtime/agentscope_adapter.py` 外，业务层没有直接 import `agentscope.*`。

### LLM 调用预算

单测 0 次；少量真实集成 2-5 次。

## Phase 3: Agent 工厂、Prompt 系统、Middleware、Mock Model

### 目标

建立统一 Agent 创建、prompt 加载、schema 校验、日志和预算机制。此阶段先用 mock model。

### 要实现

- `runtime/factory.py` 或在 adapter 内提供 `create_agent(...)`。
- `runtime/prompts.py`：从 `prompts/` 加载 md prompt。
- `runtime/middleware.py`：`SchemaValidationMiddleware`、`LoggingMiddleware`、`CostBudgetMiddleware`。
- `runtime/mock_model.py`：根据测试 fixture 返回 deterministic JSON。
- 第一批 prompt 骨架：`intake_router.md`、`context_scout.md`、`planning.md`、`task_implementation.md`、`qa_verification.md`、`review_room.md`、`delivery.md`。`shape.md`、`specification.md`、`tdd.md` 可先放空骨架，但实现阶段分别在 Phase 9a 和 Phase 8。

### 验收标准

- 不配置真实模型也能创建 mock agent。
- prompt 缺失时抛明确错误。
- mock 输出可以 parse 成目标 schema。
- schema parse 失败可触发重试一次。
- budget 超限会写入 blocked 状态。

### LLM 调用预算

0 次。

## Phase 4: Intake Router 和 Direct Answer Flow

### 目标

系统能识别用户请求进入哪条流程，并完成纯问答交付。

### 要实现

- `agents/intake_router.py`：`make_intake_router_agent()`、`call_intake_router()`。
- `workflows/direct_answer.py`。
- 路由规则：
  - 解释 / 总结 / 是什么：`direct_answer`
  - review / 检查 / PR 且不要求修复：`review_only`
  - 改 / 修 / 增加 / 删除且范围小：`lightweight`
  - 架构 / 系统 / 跨模块 / 完整流程：`full`
  - 目标不清：`needs_clarification=true`

### 验收标准

- mock 路由测试覆盖四条流程。
- Direct Answer 不触发 Write/Edit。
- 模糊请求能输出 clarification 或保守默认。

### LLM 调用预算

单测 0 次；端到端验证 5-10 次。

## Phase 5: PM Orchestrator 最小闭环

### 目标

实现 PM 编排层最小状态机。注意 PM Orchestrator 是 Python 模块，不是 Agent。

### 要实现

- `orchestration/state_machine.py`：合法状态和转换。
- `orchestration/pm_orchestrator.py`：`run_request(request, budget=...)`。
- `orchestration/cost_budget.py`。
- `agents/delivery.py` 最小版。
- Direct Answer 从 request 到 `DeliveryPackage` 的完整闭环。

### 验收标准

- Direct Answer 请求返回 `DeliveryPackage`。
- budget 超限进入 `blocked_by_budget_exceeded`。
- 非法状态转换失败。
- Lightweight 请求不会直接改文件，只会进入后续占位状态。

### LLM 调用预算

单测 0 次；端到端 3-8 次。

## Phase 6: Context Scout 和 Workspace Manager

### 目标

在计划和修改前，系统能读取真实仓库上下文，并记录工作区状态。

### 要实现

- `agents/context_scout.py`：工具 `Read/Grep/Glob/Bash`，权限 `DONT_ASK + build_readonly_probe_rules() + build_readonly_probe_deny_rules()`。
- 输出 `RepoContext`：相关文件、已有模式、测试入口、构建命令、风险提示、证据。
- `orchestration/workspace_manager.py`：Python 模块，调用 subprocess 或 workspace API 检查 `git status --short`、当前 commit、dirty files、非 git 降级。
- 使用 v2 `LocalWorkspace` 初始化和关闭。

### 验收标准

- 干净 git、dirty git、非 git 目录都有明确记录。
- Context Scout 输出带证据路径。
- dirty files 不会被忽略。
- LocalWorkspace 生命周期正确关闭。
- Context Scout 尝试运行白名单外的只读命令（如 `git checkout main`）时被 allow_rules 拦截。
- Context Scout 尝试运行 destructive 命令（如 `rm -rf <path>`）时被 deny_rules 硬拒，不触发 `RequireUserConfirmEvent`，且目标文件未被修改/删除。

### LLM 调用预算

单测 0 次；端到端 5-10 次。

## Phase 7: Task Contract 和 Lightweight Build Loop（MVP）

### 目标

完成第一个真正可用的开发闭环：小范围任务可以生成 contract、执行修改、验证、审查、交付。

### 要实现

- `agents/planning.py`：第一版只需要生成单任务 `TaskContract` 或最小 `TaskQueue`。
- `agents/task_implementation.py`：每个任务 fresh Agent，只能写 `allowed_files`。
- `agents/qa_verification.py`：只能运行 contract 指定验证命令。
- `agents/review_room.py`：合并版 review，输出 `ReviewFinding`。
- `orchestration/task_runner.py`：单任务执行状态机。
- `workflows/lightweight.py`：`route -> workspace -> scout -> planning -> contract -> impl -> verify -> review -> delivery`。

### 明确不包含

- 不包含 TDD RED 阶段。
- 不包含 Full Product Flow。
- 不包含多任务队列。
- 不包含 Review-Only Flow。
- 不包含 Debug / Browser / Documentation 专项 Agent。

### 验收标准

- 一个小文档任务可以端到端完成。
- 一个小代码任务可以端到端完成。
- 越权写文件被 PermissionRule 拒绝。
- 验证失败不能被 Delivery 标记为成功。
- ReviewRoom 的 must_fix 必须带 evidence。
- Repair loop 最多 2 次，超出后 blocked。

### LLM 调用预算

单测 0 次；端到端 6-10 次每用例。

## Phase 8: TDD RED-GREEN-REFACTOR

### 目标

给适合测试的任务加入 TDD 纪律，并用确定性逻辑校验 RED 是否成立。

### 要实现

- `agents/tdd.py`：只能写 `tests/**` 或 contract 指定的 red 文件范围。
- `RedResult.expected_failure_signature`。
- `orchestration/task_runner.py` 增加 `_verify_red(red_result)`。
- Lightweight Flow 增加可选 RED：`contract -> RED -> verify_red -> GREEN -> verification -> review`。

### 验收标准

- 测试型任务能先红后绿。
- RED 失败原因不匹配时进入 `blocked_by_red_mismatch`。
- RED skip 必须有原因。
- 文档任务不强行伪造单元测试。

### LLM 调用预算

端到端 4-8 次每用例。

## Phase 9a: Shape + Specification + Design Signoff

### 目标

实现 Full Flow 前半段：把模糊需求收敛成可确认的 Product Brief。

### 要实现

- `agents/shape.py`：输出 `ProblemFrame`。
- `agents/specification.py`：输出 `ProductBrief`。
- Design Signoff Gate：优先使用 v2 HITL；如果 POC 表明不可用，则由编排层外部确认实现。
- Full Flow 入口暂时停在 signoff 后。

### 验收标准

- 复杂请求不会直接进入实现。
- 没有 ProductBrief 不能进入 TaskQueue。
- 没有 signoff 不能进入计划。
- 用户拒绝 signoff 时进入 blocked。

### LLM 调用预算

端到端 6-12 次每用例。

## Phase 9b: TaskQueue + 多任务 TaskRunner

### 目标

让 Full Flow 能处理多任务队列。

### 要实现

- `agents/planning.py` 升级为完整 `TaskQueue`。
- `task_runner.execute_task_queue()`。
- 每个任务独立 contract、独立 Task Implementation Agent、独立 verification、独立 review。
- 任务 1 unresolved must_fix 会阻塞任务 2。

### 验收标准

- 2-3 个任务能按顺序执行。
- 中间任务失败后后续任务不会继续跑。
- 每个实现 Agent fresh context。
- 预算超限可以暂停。

### LLM 调用预算

端到端 15-30 次每用例。

## Phase 9c: Final Verification + Final Review + Global Repair Loop

### 目标

完成 Full Product Flow 的闭环。

### 要实现

- `qa_verification.py` 支持 `scope="final"`。
- `review_room.py` 支持最终级 review。
- 全局 Repair Loop：final must_fix 转成 repair tasks，最多 2 次。
- `workflows/full_product.py` 完整流程。

### 验收标准

- 一个真实小项目可以跑完整 Full Flow。
- 没有 Final Verification 不能交付。
- Final Review 有 must_fix 不能交付成功。
- 两次全局 repair 仍失败时进入 blocked。

### LLM 调用预算

端到端 25-50 次每用例。

## Phase 10: Review-Only Flow

### 目标

实现只读审查流程。

### 要实现

- `workflows/review_only.py`。
- 支持 git diff、指定文件、用户粘贴文本。
- 所有相关 Agent 强制 `PermissionMode.EXPLORE`。
- ReviewRoom 输出只读报告。

### 验收标准

- review-only 不会调用 Write/Edit。
- finding 必须带证据。
- 没证据的问题不能升级 must_fix。
- 用户要求从 review-only 变成修改时，必须重新路由到 Lightweight 或 Full。

### LLM 调用预算

端到端 4-8 次每用例。

## Phase 11: 专项 Agent 扩展

### 目标

按任务特征动态召集专项 Agent，而不是所有任务都启动全套角色。

### 要实现

- `orchestration/triggers.py`。
- `agents/debug.py`：失败诊断，只读，输出 root cause 和 minimal fix 建议。
- `agents/browser_verification.py`：Playwright / 浏览器检查，捕获 screenshot 和 console error。
- `agents/documentation.py`：只写 contract 授权的文档文件。

### 验收标准

- 测试失败触发 Debug。
- 前端任务触发 Browser Verification。
- 文档任务触发 Documentation。
- 非相关任务不启动专项 Agent。

### LLM 调用预算

端到端额外 +5 到 +15 次。

## Phase 12: 工程化和交付能力

### 目标

把系统从原型推进到日常可用工具。

### 要实现

- `runtime/events.py`：事件记录。
- `runtime/persistence.py`：TeamState 和 AgentState 持久化，Redis 或 SQLite。
- `.my-coding-team.toml` 配置。
- DockerWorkspace 集成，高风险任务可隔离执行。
- `orchestration/branch_finisher.py`：只给建议，不执行 destructive 操作。
- 完整 `DeliveryPackage`。
- 示例项目和运行材料。

### 验收标准

- 失败后可以从最近状态恢复。
- Delivery 不隐藏失败验证。
- Branch Finisher 不会 merge/reset/delete。
- 示例流程可在本地跑通。
- DockerWorkspace 真实场景验证通过。

### LLM 调用预算

单测 0 次；端到端示例 30-80 次。

## Phase 13: ReviewRoom 拆分评估

### 触发条件

满足任一条件才做：

- 5 个真实项目后，ReviewRoom 漏掉的 must_fix 中超过 30% 集中在某类问题上。
- 用户反馈 ReviewRoom “什么都讲一点，但不深入”。
- 单个 ReviewRoom prompt 超过 4000 token，维护困难。
- ReviewRoom 错误 evidence 比例超过 10%。

### 要实现

- `agents/reviewers.py`：Spec Compliance、Code Reviewer、Test Reviewer、Skeptic、Security、Performance 等拆分版。
- `agentscope.pipeline.MsgHub + sequential_pipeline` 协同。
- `orchestration/review_aggregator.py` 聚合。
- 合并版 vs 拆分版 A/B 测试。

### 验收标准

- 拆分版 must_fix 召回率至少提升 20%。
- 成本不超过合并版 2.5 倍。
- 错误 evidence 比例低于合并版。

## 3. 推荐落地顺序

```text
1. Phase 0:  package / CLI / config / tests
2. Phase 0.5: POC tests + POC_RESULTS.md
3. Phase 1:  schemas/
4. Phase 2:  runtime/agentscope_adapter.py + permission_builder.py
5. Phase 3:  prompts / middleware / mock model / create_agent
6. Phase 4:  intake_router.py + direct_answer.py
7. Phase 5:  pm_orchestrator.py + state_machine.py + delivery.py
8. Phase 6:  context_scout.py + workspace_manager.py
9. Phase 7:  planning.py + task_implementation.py + qa_verification.py + review_room.py + lightweight.py
10. Phase 8:  tdd.py + RED 校验
11. Phase 9a: shape.py + specification.py + signoff gate
12. Phase 9b: TaskQueue + 多任务 runner
13. Phase 9c: Final Verification / Final Review / Global Repair
14. Phase 10: review_only.py
15. Phase 11: debug / browser / documentation
16. Phase 12: persistence / DockerWorkspace / branch_finisher / examples
17. Phase 13: reviewers.py 拆分版，按实证决定
```

## 4. MVP 定义

MVP 是 Phase 0 到 Phase 7 的集合，必须包含 Phase 0.5。

MVP 必须具备：

- CLI 可启动。
- AgentScope v2 POC 全部通过。
- schema 可序列化。
- PermissionRule + DONT_ASK 能阻止越权写入。
- PM Orchestrator 可分流请求。
- Context Scout 可读取仓库事实。
- Workspace Manager 可记录 dirty state。
- Planning 可生成 Task Contract。
- Task Implementation 只能写授权文件。
- QA Verification 可运行指定命令。
- ReviewRoom 可阻止明显越界交付。
- Delivery 可说明结果、验证和风险。

MVP 不要求：

- TDD RED 阶段。
- Full Product Flow。
- 多任务队列。
- Review-Only Flow。
- Browser Verification。
- 拆分 reviewer。
- Branch Finisher 完整能力。
- DockerWorkspace 集成。

## 5. 风险和降级策略

### AgentScope v2 接入复杂度高

- Phase 0.5 提前暴露风险。
- 业务层只依赖 `runtime/agentscope_adapter.py`。
- 如 v2 不稳定，可替换 runtime，schema 和 orchestration 不动。

### 模型输出不稳定

- 所有关键输出必须 parse 成 Pydantic schema。
- parse 失败重试一次。
- 第二次失败写入 `blocked_by_schema_parse_failure`。

### 权限绕过风险

- 写文件和跑命令只走 v2 内置工具。
- 永不使用 `PermissionMode.BYPASS`。
- contract 外写入由 `DONT_ASK` 默认拒绝。
- review 阶段二次检查 changed files 是否超出 allowed files。

### Full Flow 过大不可调试

- 先交付 Lightweight。
- Phase 9 拆成 9a/9b/9c。
- 每个任务独立 verification 和 review。
- 每个阶段保存 TeamState。

### TDD 不适用于所有任务

- RED 可 skip，但必须记录原因。
- 文档任务使用内容缺失检查。
- UI 任务使用浏览器/截图检查。
- RED 是否符合预期由确定性逻辑校验。

### 用户工作区已有改动

- 先记录 dirty files。
- 默认不覆盖 dirty files。
- 高风险任务建议 branch 或 Docker。
- Branch Finisher 不执行 destructive 操作。

### LLM 成本失控

- 每条流程有预算。
- 每次 Agent 调用前 charge。
- repair loop 默认最多 2 次。
- 超预算进入 blocked 或等待用户确认。

## 6. 完成 Phase 12 后的目标行为

```text
User Request
  -> Intake Router
  -> PM Orchestrator
  -> Shape
  -> Specification
  -> Design Signoff
  -> Workspace Manager
  -> Context Scout
  -> Planning
  -> Task Runner
       loop:
         -> optional TDD RED
         -> Task Implementation
         -> QA Verification
         -> ReviewRoom
         -> optional Repair
  -> Final Verification
  -> Final Review
  -> optional Global Repair
  -> Branch Finisher
  -> Delivery
```

最终交付必须说明：

- 做了什么。
- 改了哪些文件。
- 运行了哪些验证。
- 哪些验证没跑以及原因。
- review 是否通过。
- 是否还有风险。
- 分支或 worktree 如何处置。
- 本次消耗了多少 LLM 调用，以及预算是多少。
