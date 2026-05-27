# My Coding Team (v3)

## Phase 0.5 runtime note

AgentScope 2.0.0 treats `PermissionMode.EXPLORE` as tool-level read-only mode and denies `Bash`, including read-only shell commands. Any read-only workflow that needs shell probes must use dedicated read tools where possible, or use `DONT_ASK` with both explicit Bash allow rules and destructive-command deny rules.

> **本文档定义系统设计，不定义施工顺序。**  
> 施工阶段、MVP 边界、验收标准和延期范围以 `construction-plan.md` 为准。本文档只回答：My Coding Team 是什么、为什么这样设计、运行时边界是什么、有哪些流程纪律和角色。

## 1. 核心定位

My Coding Team 是一套基于 AgentScope v2 的多 Agent 协同研发系统。它不是一个“超级 Agent”，也不是把 skill 仓库直接当运行时调用，而是把软件工程过程拆成可控的阶段、契约、验证和审查。

一句话定义：

> AgentScope provides the single-agent runtime. Our orchestration layer runs the team. agent-skills shapes the roles. superpowers disciplines the workflow.

中文表达：

> AgentScope 提供单 Agent 运行时；我们自己的 Python 编排层管理团队协同；agent-skills 启发角色能力拆分；superpowers 提供工程纪律、阶段门、TDD 和分支收尾方法。

## 2. 设计目标

系统要解决的不是“让 LLM 尽量聪明地改代码”，而是让 LLM 的改动过程可控、可验证、可恢复：

- 复杂需求先收敛目标和规格，再进入计划。
- 计划必须拆成可执行、可验证、可审查的小任务。
- 每个任务都要有文件范围、验证命令和停止条件。
- 写权限、命令权限由工具层硬约束，不依赖 Agent 自觉。
- 验证失败、Review must_fix、schema parse 失败都不能被包装成成功。
- PM Orchestrator 用确定性 Python 做阶段推进和裁决，LLM 只负责需要判断、分析、生成的节点。

## 3. AgentScope v2 能力边界

### 3.1 v2 直接提供，我们复用

- `Agent`：单 Agent ReAct 推理-行动循环。
- `Toolkit`：统一管理工具、MCP、skills/loaders、tool groups。
- 内置工具：`Bash`、`Read`、`Write`、`Edit`、`Grep`、`Glob`。
- 权限系统：`PermissionContext`、`PermissionMode`、`PermissionRule`、`PermissionBehavior`。
- Human-in-the-Loop：`RequireUserConfirmEvent` / `UserConfirmResultEvent`。
- 工作区：`LocalWorkspace`、`DockerWorkspace`、`E2BWorkspace`。
- 状态：`AgentState`。
- 中间件：`MiddlewareBase`。
- 协同原语：`MsgHub`、`sequential_pipeline`、`fanout_pipeline`、`observe()`。

### 3.2 v2 不直接提供，我们自己写

- 多 Agent 工作流状态机。
- 阶段门和 PM 决策。
- TaskQueue 调度。
- TaskContract / RepairContract 注入。
- Review must_fix 聚合和裁决。
- 跨 Agent 共享的 `TeamState`。
- 交付前的最终验收规则。

### 3.3 明确废弃的旧假设

- 不再使用 v1 `ReActAgent`。
- 不再依赖 v1 `PlanNotebook`。
- 不使用 `__call__(msg)`，改用 `reply()` / `reply_stream()`。
- 不使用 `enable_meta_tool=True`，工具组通过 `Toolkit(tool_groups=[...])` 管理。
- 不自造 `RestrictedFileEditTool` / `RestrictedShellTool`，除非 POC 证明 v2 权限不满足需求。

## 4. 架构分层

```text
User / CLI / UI
   |
   v
PM Orchestrator --------------+
(Python state machine)         |
   |                           |
   v                           |
Workflows                      |
(direct_answer / lightweight / full / review_only)
   |
   v
Agents                         TeamState
(AgentScope v2 Agent factories) <----- schemas / results / budget / state
   |
   v
AgentScope Runtime
(Agent / Toolkit / PermissionContext / Workspace / Middleware)
```

### 4.1 编排层

`my_coding_team/orchestration/` 是系统核心。它负责：

- 维护 `TeamState`。
- 推进状态机。
- 调用 Agent 并 parse schema。
- 执行阶段门。
- 处理 budget、retry、blocked 状态。
- 把 Review must_fix 转成 RepairContract。
- 决定 Delivery 是成功、失败、blocked 还是 partial。

### 4.2 Agent 层

`my_coding_team/agents/` 只放 Agent 工厂和调用包装。每个 Agent 是一组配置：

```text
(system_prompt, toolkit, permission_context, model_config, middleware, workspace/offloader)
```

Agent 不直接推进全局流程，不修改 `TeamState`，不决定是否交付。

### 4.3 Runtime 适配层

`my_coding_team/runtime/agentscope_adapter.py` 是唯一直接 import `agentscope.*` 的模块。业务层通过适配层创建 Agent、Workspace、PermissionRule，方便未来替换运行时。

## 5. 核心流程

### 5.1 Direct Answer Flow

适合解释、总结、方案分析、概念问答。

```text
Intake Router
  -> PM Orchestrator
  -> Delivery(answer-only)
```

规则：

- 默认不读取仓库。
- 不写文件。
- 如果问题明确依赖仓库上下文，必须升级为带 Context Scout 的只读流程。

### 5.2 Lightweight Flow

适合明确的小 bug、小文档、小配置、小范围重构。

```text
Intake Router
  -> Workspace Manager
  -> Context Scout
  -> Planning / Task Contract
  -> Task Implementation
  -> QA Verification
  -> ReviewRoom
  -> optional Repair
  -> Delivery
```

规则：

- 不经过完整 Shape / Spec / Design Signoff。
- 仍必须有 Task Contract。
- 仍必须限制 `allowed_files` 和 `verification_commands`。
- 如果任务变复杂，PM 升级到 Full Product Flow。
- 在 Phase 7 MVP 中，Lightweight 不包含 TDD RED；TDD 从 Phase 8 加入。

### 5.3 Full Product Flow

适合新功能、架构改造、跨模块变更、需求不够清晰的复杂任务。

```text
Intake Router
  -> Shape
  -> Specification
  -> Design Signoff
  -> Workspace Manager
  -> Context Scout
  -> Planning as TaskQueue
  -> Execute Task Queue
       loop per task:
         -> Task Contract
         -> optional RED (Phase 8+)
         -> GREEN / implementation
         -> QA Verification
         -> ReviewRoom
         -> optional Repair
  -> Final Verification
  -> Final Review
  -> optional Global Repair
  -> Branch Finisher
  -> Delivery
```

规则：

- 没有 ProductBrief，不能进入 TaskQueue。
- 没有 Design Signoff，不能进入计划。
- 当前任务有 unresolved must_fix，不能进入下一个任务。
- Final Verification 或 Final Review 失败，不能交付为成功。

### 5.4 Review-Only Flow

适合 PR/diff 检查、指定文件审查、只读风险分析。

```text
Intake Router
  -> Context Scout / Diff Collector
  -> ReviewRoom(EXPLORE)
  -> Delivery Summary
```

规则：

- 默认不修改代码。
- 全部 Agent 强制 `PermissionMode.EXPLORE`。
- 没有 evidence 的问题不能升级为 must_fix。
- 用户要求“顺手修一下”时，需要重新路由到 Lightweight 或 Full。

## 6. 状态机

```text
received
  -> routed
  -> answering_directly
  -> checking_workspace
  -> scouting_context
  -> planning_task
  -> executing_task
  -> verifying_task
  -> reviewing_task
  -> repairing_task
  -> shaping
  -> specifying
  -> awaiting_design_signoff
  -> planning_task_queue
  -> final_verifying
  -> final_reviewing
  -> finishing_branch
  -> delivering
  -> done
```

异常状态：

- `blocked_by_user_decision`
- `blocked_by_dirty_worktree`
- `blocked_by_missing_context`
- `blocked_by_contract_error`
- `blocked_by_failing_baseline`
- `blocked_by_tool_failure`
- `blocked_by_schema_parse_failure`
- `blocked_by_budget_exceeded`
- `blocked_by_red_mismatch`
- `blocked_by_max_repair_retries_exceeded`
- `cancelled`

## 7. Agent 角色地图

> 阶段启用顺序以 `construction-plan.md` 为准。这里仅说明角色职责。

| 角色 | 类型 | 职责 | 权限 |
|---|---|---|---|
| PM Orchestrator | Python 模块 | 全局状态机、阶段门、预算、裁决、repair 派发 | 不直接用 LLM |
| Intake Router | LLM Agent | 路由、风险、是否需要仓库修改 | `EXPLORE（无 Bash）` |
| Delivery | LLM Agent | 生成用户可读交付包 | 无工具或只读 |
| Context Scout | LLM Agent | 搜索仓库事实、相关文件、测试入口、命令 | `DONT_ASK + 只读白名单` |
| Workspace Manager | Python 模块 | dirty state、baseline、workspace 初始化 | subprocess / Workspace API |
| Planning | LLM Agent | 生成 TaskContract 或 TaskQueue | `DONT_ASK + 只读白名单` |
| Task Implementation | LLM Agent | 单任务最小实现和必要 refactor | `DONT_ASK` + allowed files |
| QA Verification | LLM Agent | 运行 contract 指定验证命令 | `DONT_ASK` + allowed bash prefixes |
| ReviewRoom | LLM Agent | 合并 spec/code/test/skeptic 审查 | `DONT_ASK + 只读白名单` |
| TDD | LLM Agent | RED 测试或失败检查 | `DONT_ASK` + tests/** |
| Shape | LLM Agent | 收敛模糊需求，输出 ProblemFrame | `EXPLORE（无 Bash）` |
| Specification | LLM Agent | 输出 ProductBrief 和验收标准 | `EXPLORE（无 Bash）` |
| Branch Finisher | Python 模块 | 分支/工作区处置建议 | 不执行 destructive 操作 |
| Debug | LLM Agent | 失败诊断，输出 repair 建议 | `DONT_ASK + 只读白名单` |
| Browser Verification | LLM Agent / Tool wrapper | 浏览器检查、截图、console error | 限定命令/工具 |
| Documentation | LLM Agent | 文档修改 | contract 限定文件 |

## 8. 权限模型

### 8.1 只读 Agent

适用：Intake、Shape、Specification、Context Scout、Planning、ReviewRoom、Debug。
按是否需要 Bash 分两组：
```text
A. 纯文本只读（Intake、Shape、Specification）
textPermissionMode.EXPLORE
工具集限定为 Read/Grep/Glob
```
含义：允许只读读取、grep、glob；不使用 Bash。
B. 需要 Shell 探查（Context Scout、Planning、ReviewRoom、Debug）
```text
textPermissionMode.DONT_ASK
allow_rules = build_readonly_probe_rules()
deny_rules  = build_readonly_probe_deny_rules()
```
含义：在 DONT_ASK 下显式白名单一组只读 Bash 前缀（git status、git log、git diff、git show、ls、cat、head、tail、wc、find、rg、tree、pwd、file 等），其余 Bash 调用一律拒绝。

> 原因：Phase 0.5 POC 实测两点：(1) AgentScope 2.0.0 的 PermissionMode.EXPLORE 在工具层直接拒绝 Bash，包括只读命令；(2) v2 内置安全层对 rm -rf 等 destructive 命令会发 RequireUserConfirmEvent，不会因为“不在 allow_rules 里”就变成 denial。因此只读 Agent 既不能用 EXPLORE+Bash，也不能只靠 allow_rules，必须 allow_rules + deny_rules 双层配置。

### 8.2 写代码 Agent

适用：Task Implementation。

使用：

```text
PermissionMode.DONT_ASK
allow_rules["Read"] = **
allow_rules["Write"] = TaskContract.allowed_files
allow_rules["Edit"] = TaskContract.allowed_files
allow_rules["Bash"] = TaskContract.verification_commands converted to prefixes
```

### 8.3 写测试 Agent

适用：TDD。

使用：

```text
Write/Edit: tests/** 或 TaskContract.red_allowed_files
Bash: red_verification_command
```

### 8.4 验证 Agent

适用：QA Verification。

使用：

```text
Read: **
Bash: contract 指定命令前缀
Write/Edit: 不允许
```

### 8.5 禁止项

- 永远不使用 `PermissionMode.BYPASS`。
- 不让 reviewer 写代码。
- 不让 Delivery 运行修改命令。
- 不让 Branch Finisher 自动 merge/reset/delete。
- 无人值守的只读 probe Agent 不允许仅配置 allow_rules 而省略 deny_rules；否则 destructive 命令会变成 HITL 卡点而非硬拒。

## 9. 协作协议

### 9.1 结构化输出

每个 Agent 的最终输出必须能 parse 成 Pydantic schema。推荐统一外层信封：

```json
{
  "agent": "ReviewRoom",
  "stage": "task_review",
  "status": "changes_requested",
  "summary": "发现一个阻断问题。",
  "data": {},
  "evidence": ["tests/test_router.py::test_route failed"],
  "confidence": 0.86
}
```

### 9.2 Evidence First

以下判断必须带 evidence：

- 代码正确性。
- 测试是否通过。
- 安全、权限、数据风险。
- 性能风险。
- 浏览器/截图观察。
- must_fix 升级。

### 9.3 Must Fix 不能泛化

只有以下问题可以升级 must_fix：

- 功能错误。
- 核心 scope 没完成。
- 验证失败或验证不可信。
- 安全、数据、权限、兼容性风险。
- 用户核心路径不可用。
- 越权文件修改。

### 9.4 Retry 和 blocked

- schema parse 失败：重试一次。
- repair loop：默认最多 2 次。
- RED mismatch：不自动修，先 blocked。
- budget 超限：blocked 或等待用户确认继续。

## 10. ReviewRoom 策略

第一版 ReviewRoom 是合并版，不拆多个 reviewer。它必须在一次输出里覆盖四个视角：

- Spec Compliance
- Code Quality
- Test Quality
- Skeptical Concerns

输出分级：

- `must_fix`：阻断交付。
- `should_fix`：记录，默认不阻塞，除非 PM 判断影响后续任务。
- `nice_to_have`：不进入当前返工。

拆分版 reviewer 只在 Phase 13 且满足实证触发条件后实现。

## 11. 成本预算口径

| 流程 | 预算参考 | 说明 |
|---|---:|---|
| Direct Answer | 1-2 次 | Intake + Delivery |
| Review-Only | 4-8 次 | Intake + Scout + Review + Delivery |
| Lightweight MVP | 6-10 次 | Intake + Workspace + Scout + Planning + Impl + Verify + Review + Delivery |
| Lightweight with TDD | 8-14 次 | 额外 RED |
| Full Product 3 tasks | 25-50 次 | Shape/Spec/Signoff + TaskQueue + final |
| Full Product 10 tasks | 50-70+ 次 | 必须预算前置检查 |

预算由 PM Orchestrator 记录在 `TeamState.llm_calls_used` 和 `TeamState.llm_calls_budget`。

## 12. 成功标准

系统达到日常可用时，应满足：

- 请求能正确分流。
- 复杂需求必须经过设计确认。
- 改代码前检查工作区状态。
- 计划能拆成可执行任务。
- 每个任务都有 TaskContract。
- allowed_files 由 PermissionRule 硬约束。
- 适合测试的任务走 TDD。
- RED 是否符合预期由确定性逻辑判断。
- 每个任务有验证和 Review。
- 最终交付前有 Final Verification 和 Final Review。
- Branch Finisher 只建议，不执行 destructive 操作。
- Delivery Package 说明修改、验证、失败项、剩余风险和下一步。
