# B2 工具框架复用审计与 B6 接口准备

本文件根据四个工程的实际源码与测试源码编写。路径均相对于 Git 根目录。B2 只交付此审计文档；没有新增 Tool Planner、MCP Client、MCP Server 或运行时工具接口。下文 B4/B6 目标路径均是提案，不代表文件已创建或功能已接入。

审计状态：源码与测试源码已检查；本文涉及的旧工程测试本轮未运行，执行状态为 **NOT TESTED**。不能把存在测试文件等同于测试通过，也不能把离线 provider 或 MockTransport 结果等同于真实服务验收。主工程本轮 CRM 测试结果由 B2 总报告记录。

## 1. 复用决策

| 功能 | 实际来源文件 | 当前或建议目标 | 决策 | 兼容性与必要处理 | 已有测试证据（源码） |
|---|---|---|---|---|---|
| 主 Orchestrator | `04_stage2_unified_agent/app/agent/orchestrator.py` | 原文件 | KEEP | 保留 `answer(user_id, message, history, session_id, attachment)`、三分类 Router、附件与双来源证据链 | `04_stage2_unified_agent/tests/integration/test_orchestrator_routing.py`、`test_web_search_orchestration.py` |
| 唯一 LLM 接口 | `04_stage2_unified_agent/app/llm/client.py` | 原文件 | KEEP | 当前契约为 `answer(prompt: str) -> str`，FakeLLM 的 `last_prompt` 可证明上下文传递；当前没有原生工具选择接口 | 04 现有 Orchestrator 回归及 B2 上下文测试 |
| 单一工具目录 | `01_agent/src/deutschpath/tools/registry.py`、`base.py` | B6 建议 `04_stage2_unified_agent/app/tools/registry.py` | DEFER | 选择 01 `ToolRegistry` 的名称唯一、定义与执行绑定结构；未来 ADAPT 到 04，无旧 Router 依赖 | `01_agent/tests/unit/test_tool_registry.py` |
| 工具定义、调用、结果 DTO | `01_agent/src/deutschpath/domain/schemas.py` 的 `ToolDefinition`、`ToolCall`、`ToolResult` | B6 同一工具边界 | DEFER | 优先复用带 `call.id` / `tool_call_id` 的契约，便于 MCP 结果关联；不复制整份混合业务 schemas 文件 | `01_agent/tests/unit/test_tool_registry.py`、`test_deepseek_tools.py` |
| 执行器重验证与异常边界 | `02_crm_agent/app/tools/executor.py`、`execution_models.py` | B6 建议 `04_stage2_unified_agent/app/tools/executor.py` | DEFER | 选择 02 `ToolExecutor.execute` 的先校验后执行、受控失败模式；未来 ADAPT 到同一个 01 风格目录与 04 状态对象，不带入默认建库工厂 | `02_crm_agent/tests/test_tool_execution.py` |
| 02 第二套 schema/handler 目录 | `02_crm_agent/app/tools/registry.py`、`execution_registry.py` | 不整体迁入 | DISCARD | 其单独两个目录有价值，但与上述单一目录职责重合；保留旧文件，仅不纳入主工程 | `02_crm_agent/tests/test_function_calling.py`、`test_tool_execution.py` |
| 参数校验 | `01_agent/src/deutschpath/tools/base.py`；`02_crm_agent/app/tools/function_calling.py` 的 `validate_arguments` / `_validate_value` | B6 工具请求模型及验证边界 | DEFER | 02 比 01 多枚举、上下界、空值、数组检查；只复用已支持约束与测试，复杂 MCP schema 使用成熟验证能力，不能视旧函数为完整 JSON Schema 实现 | 上述 registry / function calling / execution 测试 |
| 一次模型工具调用 | `01_agent/src/deutschpath/tools/function_calling.py` | B6 规划边界参考 | DEFER | `FunctionCallingService.run` 调用一次 `llm.invoke` 后顺序执行全部 calls；无写入确认、总调用数或超时限制，不可直接用于写库 | `01_agent/tests/unit/test_tool_registry.py::test_function_calling_is_one_turn_and_sequential` |
| CRM 工具定义与 Handler | `02_crm_agent/app/tools/definitions.py`、`handlers.py` | B6 CRM 工具 Adapter → 04 `app/users/` | DEFER | 复用等级/目标/偏好/事件操作参数及调用方式；`external_user_id`、整数 customer_id、`CustomerState` 必须适配为 04 user_id / UserState，不接旧 CRM DB | `02_crm_agent/tests/test_function_calling.py`、`test_tool_execution.py` |
| 02 工具选择器与规则 provider | `02_crm_agent/app/tools/function_calling.py` 的 `FunctionCaller`、`provider.py` | 不整体迁入 | DISCARD | 绑定旧 CRM 五分类 Route，并且默认为规则选择；不能替代 04 三分类 Router，也不能宣称已完成模型选择工具 | `02_crm_agent/tests/test_function_calling.py` |
| Agent Loop | `01_agent/src/deutschpath/agent/loop.py` | B6 受限工具回合参考 | DEFER | `AgentRunner.run` 有轮数、调用结果反馈、用户一致性检查；不创建第二套顶层 AgentRunner，不覆盖 04 RAG/Web/附件链 | `01_agent/tests/unit/test_agent_loop.py`、`test_agent_history.py` |
| Agent State | `01_agent/src/deutschpath/agent/state.py` | B6 请求内工具状态参考 | DEFER | `AgentState` 为内存对象，不能代替 04 SQLite UserState / ChatRepository；只能按需提取调用记录及状态字段 | `01_agent/tests/unit/test_agent_loop.py` |
| Checkpoint | `01_agent/src/deutschpath/agent/checkpoint.py` | 无已实现可迁移内容 | DEFER | 实际文件只有 `Checkpoint persistence placeholder` docstring，无保存、读取、恢复实现；不能声明复用成功 | 未发现对应 checkpoint 行为测试 |
| DeepSeek 工具消息编码/解析及错误分类 | `01_agent/src/deutschpath/llm/deepseek.py`、`llm/client.py`、`domain/errors.py` | B6 适配到 04 `app/llm/` | DEFER | 可提取 `_message_payload`、`_tool_payload`、`_parse_tool_calls`、错误映射和客户端关闭方式；保持 04 `answer` 兼容，不同时运行第二套 LLM 配置/Provider | `01_agent/tests/unit/test_deepseek_client.py`、`test_deepseek_tools.py`（MockTransport） |
| 01 固定五工具及旧工厂 | `01_agent/src/deutschpath/tools/core.py`、`learning.py`、`knowledge.py`、`profile.py`；`application/service.py` | 不整体迁入 | DISCARD | 04 已有 RAG/UserState，旧 score/target_job/target_year 与 04 模型不同；工厂会初始化 E5、旧 Chroma 与 SQLite，不适合直接导入 | `01_agent/tests/unit/test_tools_core.py`；旧 integration 测试显式构建 E5，B2 不运行 |
| 03 到 01 的 Agent Adapter | `03_deutsch_chat/src/deutsch_chat/adapters/agent_adapter.py` | 保留 04 `app/chat/service.py` | DISCARD | 03 每次 ask 创建 01 runner，并转换 visible history、关闭 LLM；04 已有对应 ChatService→Orchestrator 链，不再接 01 工厂 | `03_deutsch_chat/tests/unit/test_agent_adapter.py`、`tests/integration/test_agent_bridge.py` |
| SQLite 只读执行 | `02_crm_agent/app/sql_agent/executor.py` | B4 Database MCP 的内部数据库 Adapter | DEFER | 复用 `mode=ro`、authorizer、progress handler、fetchmany 上限、连接 finally close；改为受控业务数据库路径，补读取表授权 | `02_crm_agent/tests/test_sql_agent.py` |
| SQL 词法过滤及 schema allowlist | `02_crm_agent/app/sql_agent/guard.py`、`schema.py` | B4 Database MCP 查询安全边界 | DEFER | 正则过滤只能作为辅助；旧表名为 customers/learning_profiles/interactions/learning_events，不能直接当新业务库白名单 | `02_crm_agent/tests/test_sql_agent.py`、`test_sql_generator_llm.py` |
| SQL 生成服务 | `02_crm_agent/app/sql_agent/generator.py`、`service.py` | 无 B2 目标 | DEFER | 旧 SQLAgentService 为自然语言 CRM 分析，非 MCP 协议；不把此接口误称为 MCP Server | `02_crm_agent/tests/test_sql_agent.py`、`test_sql_generator_llm.py` |

本表的 DISCARD 表示不迁移重复或不适用实现，不表示删除历史文件。B2 此项审计新增业务代码 **0 行**，新增依赖 **0 项**，删除重复实现 **0 个文件**。REUSE / ADAPT 的运行时迁移尚未发生；表中未来适配方案均明确为 DEFER。

## 2. 真实接口差异和限制

01 的 `LLMClient.invoke(messages, tools=None, tool_choice=None) -> LLMResponse` 使用结构化消息、原生工具返回与工具调用 ID。04 的 `LLMClient.answer(prompt) -> str` 只返回文本，两者不能直接互换。01 的 tool-call parsing / HTTP 错误映射较完整，可在 B6 提取到当前 Provider；应保留 04 `answer` 入口，并让它与未来工具调用能力使用同一 Provider、同一配置及同一资源生命周期。B2 不提前修改接口。

01 的 Registry 本身只有少量内部依赖，注册同名工具会报错，执行失败返回结构化 `ToolResult`。它的 `validate_arguments` 只检查 required、additionalProperties 与几个基础类型，**不执行 schema 中的 minimum/maximum 等所有约束**。02 参数校验支持更多约束，但 object 不校验嵌套字段、array 仅按字符串列表处理；均不足以直接验证所有 Database/OCR MCP 输入。B6 要将现有正确校验规则与负例测试保留，使用 Pydantic 或协议配套的成熟校验能力完成严格参数边界，不另写通用 JSON Schema 引擎。

02 的 `ToolExecutor` 已有 `_normalize_arguments`、执行前再次校验、受控错误结果和 handler 返回类型检查。`build_default_executor()` 同时调用旧 `get_settings()`、`Database.initialize_schema()` 和旧知识库搜索工厂，不能复制进主应用。未来只迁移无副作用执行边界，并注入 04 服务或 MCP Client Adapter。现有 `_safe_error` 对 ValueError/TypeError/KeyError 会保留消息文本，因此不能将其描述为全面脱敏实现。

01 的 `AgentRunner` 每轮调用一次模型并反馈所有工具结果，`max_steps` 限定为 1–10；它计数的是**工具轮数**，单轮工具数量未受独立上限约束，也没有写入幂等键或用户确认机制。其 `_USER_SCOPED_TOOLS` 只覆盖三个旧工具名称，不能视为通用权限模型。02 的等级/目标更新测试包含同值更新不改状态，而 `add_learning_event` 的测试明确要求重复调用产生两条不同记录，所以并没有通用防重复写入能力。

02 SQL Executor 的只读 URI 和 authorizer 确实限制写入、ATTACH、PRAGMA 与 load_extension，并在 `finally` 关闭连接。`SQLGuard` 通过 FROM/JOIN 正则检查表名；它不是 SQL parser。authorizer 当前没有按 `SQLITE_READ` 检查表名和列名，因此不能将“只读”宣称为“只允许指定业务表读取”。B4 需要配置固定业务库路径、允许表/列范围并在实际数据库执行层实施读取授权；旧正则和旧 schema 常量不能作为唯一边界。MCP 业务数据库必须与聊天/CRM DB 分开。

03 的 `AgentAdapter.ask` 已经做了 visible history 约束、错误包装和 LLM close，但依赖 `01_agent` 的 `build_agent`；此工厂会构建另一套 E5/RAG/SQLite/Router/AgentRunner。复用该完整 Adapter 会引入用户明确禁止的第二条业务主链。B2 保留 04 `ChatService.send_message`，仅保留旧 Adapter 测试中历史隔离和失败不伪造回答的检查目标。

## 3. B6 最小接口建议（未实施）

1. **一个工具目录。** 从 01 `ToolRegistry` 迁移最小注册、查找、定义列举代码。将本地 CRM Service Adapter 和两个 MCP Server 允许暴露的工具放入该目录；目录定义及可执行对象保持一一对应。02 的第二套 schema registry / execution registry 不并行接入。
2. **一个执行边界。** 从 02 `ToolExecutor.execute` 提取并适配重验证、handler 调用和失败结果处理，使用上一步同一目录。工具 result 采用 01 call ID 关联方式，并按需吸收 02 `state_changed` 与 metadata；不强制依赖旧 CustomerState。MCP 连接、initialize、超时与断线由官方 SDK Client Adapter 实现，普通 Python handler 不能冒充 MCP。
3. **保留 Router 三分类。** 04 `app/routing/models.py` 的 `rag / web_search / no_tool` 与 `RouteDecision.mixed_sources` 不变。工具规划是由 Orchestrator 按需委托的独立步骤，不新增 MCP intent，不迁移 02 五分类 Route，也不再调用旧 Router。
4. **保留唯一 Orchestrator 与 Provider。** 04 仍拥有用户状态、聊天历史、附件、RAG/Web 与最终回复的控制权。B6 从 01 抽取有限轮数与 observation feedback 思路，置于其受控工具步骤内部；复用 01 Function Calling 编解码并适配同一 04 Provider。不要挂接另一个完整 AgentRunner，也不要用字符串拼接把工具执行伪装成原生 Function Calling。
5. **建立明确执行权限。** 由当前本地应用的会话上下文提供 user_id 和允许操作，避免信任模型自己生成的身份。B6 为每次写入展示内容并取得确认，为一次写入绑定幂等标识，同时分别限制工具轮数、工具调用总数和超时。上述能力目前不能从旧框架完整复用，应在 B6 以最小胶水补齐。
6. **保持可追踪与不伪造成功。** 使用 call ID 关联模型请求、实际 MCP 请求、结果和最终响应。Checkpoint 目前不存在；若现有消息存储不足以承载可靠工具审计，先提交可回滚迁移方案，获得数据库变更授权后再实施，不能提前假定已有工具日志表。

未来调用关系：`04 ChatService → 04 UnifiedOrchestrator → 原三分类 Router / 原 RAG-Web 证据链 → 按需工具步骤 → 一个 ToolRegistry + 一个 Executor → 官方 MCP Client Adapter → Database/OCR MCP Server → ToolResult → ContextBuilder → 同一个 LLM Provider → ChatRepository`。这描述可选步骤，普通聊天不需要逐项经过所有模块。

## 4. B3 与 B6 可继承的测试

- B3：保留 `04_stage2_unified_agent/tests/integration/test_orchestrator_routing.py`、`test_web_search_orchestration.py` 对路由、明确联网请求受控失败、附件与混合来源的断言。不要用历史成绩代替本轮回归，Router 98% 和 Tavily 实时服务验收仍是独立指标。
- B6 Registry / Executor：移植 `01_agent/tests/unit/test_tool_registry.py` 的重名、未知工具、额外参数、类型错误及结果关联测试；移植 `02_crm_agent/tests/test_tool_execution.py` 的重验证、handler 异常、未知用户、同值更新与 before/after 断言。将旧 Repository fixture 改为 04 服务或隔离 MCP fixture。
- B6 Provider：移植 `01_agent/tests/unit/test_deepseek_tools.py` 的工具 schema 编码、assistant/tool 消息、调用 ID 和畸形 JSON 拒绝测试；从 `test_deepseek_client.py` 保留超时、鉴权、限流、服务端错误映射。这些离线测试通过也不等同于真实 DeepSeek 验收。
- B6 请求状态：参考 `01_agent/tests/unit/test_agent_loop.py` 和 `test_agent_history.py` 的轮数终止、失败结果回传、跨用户拒绝、显式历史隔离；必须另外覆盖总调用数、超时、确认前不写、重复确认不重复插入、MCP 断连与真实协议交互。不能仅运行旧 loop 测试宣称新工具闭环完成。
- B4 SQL：保留 `02_crm_agent/tests/test_sql_agent.py` 中只读执行、写操作拒绝、行数上限、未知列受控失败断言，并补读取授权、固定数据库路径及复杂 SQL 绕过用例。旧文件混有 TestClient 测试，迁移时只提取有用断言；遵守现有 Windows TestClient BLOCKED 边界，使用主工程真实 Uvicorn 模式验收 HTTP。

本轮未运行旧 `01_agent/tests/integration/test_tools_integration.py`，该文件显式初始化 MultilingualE5Embedding，可能加载或下载模型。B2 离线验收继续使用 04 FakeLLM、deterministic embedding 和隔离数据路径。B4/B6 的 SDK 版本、真实协议与 MCP Inspector 尚未实施或验证，状态为 **NOT TESTED**。
