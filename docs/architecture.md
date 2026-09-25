# Creo Architecture

> 状态：与 MVP 实现保持同步。架构级变更必须先更新 ADR，再更新本文。

---

## 1. 系统总览

```text
User
  ↓
React Agent UI (frontend/)
  ↓  POST /api/chat  (SSE 响应)
FastAPI (backend/app/api/)
  ↓
Services (backend/app/services/)      ← Session 存储边界（当前：内存）
  ↓
Agent Runtime (backend/app/agent/runtime.py)
  ↓
DeepAgents (backend/app/agent/agent.py)
  ↓
LLM + Tools
  ↓
Creo Agent Events (SSE) → React Event Dispatcher → UI State
```

Creo 是前后端分离的单体仓库（monorepo）：

- `frontend/`：React 19 + TypeScript (strict) + Vite + Tailwind CSS，包管理器 **pnpm**（版本锁定于 package.json `packageManager`，仓库配置在 `pnpm-workspace.yaml`）。SPA，无 Next.js。
- `backend/`：Python 3.12+ / FastAPI / DeepAgents / uv。无数据库。

---

## 2. 核心链路（Streaming）

```text
React
 ↓ POST /api/chat { session_id, message }
FastAPI Route（校验 + 组装，无 Agent 逻辑）
 ↓
AgentRuntime.stream_events()（AsyncIterator[AgentEvent]）
 ↓ DeepAgents graph.astream(messages 模式 + updates 模式, subgraphs)
LLM / Tools
 ↓ Runtime 把原始流转换为 Creo AgentEvent
SSE（text/event-stream）
 ↓ useSSE（fetch ReadableStream 逐帧解析）
agentStore.applyAgentEvent() → UI State
```

**禁止**：等 Agent 完成后一次性返回完整答案。流式是硬性要求。

---

## 3. 模块职责

### Frontend

| 路径 | 职责 |
| --- | --- |
| `src/types/agent.ts` | Agent Event / Message / ToolInvocation 类型（与后端 events.py 对齐） |
| `src/lib/` | `utils.ts`（cn）、`sse.ts`（纯 SSE 帧解析器） |
| `src/services/agentApi.ts` | 唯一的网络出口：streamChat / sessions API |
| `src/hooks/useSSE.ts` | fetch 流式 SSE 的 React 封装（AbortController、生命周期） |
| `src/hooks/useAgent.ts` | 发送消息、事件分发到 store、会话管理 |
| `src/stores/agentStore.ts` | zustand store；`applyAgentEvent` 为纯函数（可测试） |
| `src/components/agent/` | Agent 状态行（Thinking / Running…） |
| `src/components/chat/` | 消息气泡、Markdown 渲染、代码块、Composer、空状态 |
| `src/components/tool/` | Tool Call 卡片（一等公民，三态可视化） |
| `src/components/layout/` | Header / Sidebar / 主题切换 |
| `src/components/ui/` | shadcn 风格基础组件（Button / Input / Badge / Spinner） |

### Backend

| 路径 | 职责 |
| --- | --- |
| `app/main.py` | FastAPI 工厂、CORS、日志初始化 |
| `app/api/routes/chat.py` | POST /api/chat → SSE StreamingResponse（编码，不做逻辑） |
| `app/api/routes/sessions.py` | 会话列表 / 历史消息 / 删除 |
| `app/api/routes/health.py` | GET /api/health |
| `app/agent/agent.py` | 构建 DeepAgents 图（唯一 import deepagents 的地方） |
| `app/agent/runtime.py` | 把 DeepAgents 原始流转换为 Creo AgentEvent |
| `app/agent/model.py` | LLM 模型初始化（init_chat_model） |
| `app/agent/config.py` | Agent 相关配置（模型名、系统提示词） |
| `app/tools/demo_tools.py` | calculator / get_current_time（Tool 独立，Agent 只注册） |
| `app/models/chat.py` | 请求 / 响应 Pydantic 模型 |
| `app/models/events.py` | **Creo Agent Event 协议（单一事实来源）** |
| `app/services/session_service.py` | 会话存储（当前内存实现，接口隔离） |
| `app/core/config.py` | pydantic-settings 配置（前缀 `CREO_`） |
| `app/core/logging.py` | 日志初始化 |

---

## 4. Agent Event Protocol

前端**不依赖 DeepAgents / LangGraph 内部对象**。协议详见 [ADR-0002](decisions/0002-agent-event-protocol.md)，事件类型：

```text
run_started     流开始（含 runId）
message_start   一段助手消息开始（含 messageId）
message_delta   助手文本增量
message_end     一段助手消息结束
tool_start      工具调用开始（toolCallId / toolName / args）
tool_result     工具返回（toolCallId / result / isError）
error           出错（message）
run_finished    流结束（runId）
```

未来扩展（**当前不实现**，扩展前先改 ADR-0002）：

```text
approval_required / state_update / artifact_created / artifact_updated
source_added / agent_status
```

---

## 5. Session 模型

- 请求体：`{ "session_id": "...", "message": "..." }`，`session_id` 由前端生成（UUID）。
- 会话元数据存储在 `SessionService`（**接口隔离**：当前为内存实现，未来可替换为 Redis / PostgreSQL，Route 与 Runtime 不感知存储细节）。
- 对话记忆：DeepAgents 图使用 LangGraph checkpointer（`MemorySaver`，thread_id = session_id）。重启即丢失，属 MVP 预期行为。
- 历史读取：`GET /api/sessions/{id}/messages` 从 Runtime / checkpointer 还原为 Creo 消息结构。

---

## 6. Tools

- Tool 独立存在于 `backend/app/tools/`，Agent 只负责注册（`create_deep_agent(tools=...)`）。
- 新增 Tool **不能修改 UI 核心**：UI 通过 `tool_start` / `tool_result` 事件泛化渲染任何工具。
- 当前：`calculator`（AST 安全求值）、`get_current_time`。
- 预留（不实现）：`web_search` / `database` / `file_search` / `python` / `mcp` / `knowledge_search`。

---

## 7. 扩展边界（预留，不实现）

```text
                    Creo
                      │
        ┌─────────────┼─────────────┐
        ↓             ↓             ↓
      Agent         Tools        Knowledge
        │             │             │
        ↓             ↓             ↓
     DeepAgents       MCP          RAG
        │
        ↓
     Artifacts
```

| 未来方向 | 当前预留的接缝 |
| --- | --- |
| RAG / Knowledge | `Knowledge` 独立顶层模块；事件协议可加 `source_added` |
| MCP | Tools 目录新增 `mcp.py`，UI 泛化渲染即可 |
| Multi-Agent | DeepAgents subagents；事件可加 `agent_status` |
| Artifacts | 事件协议可加 `artifact_created/updated` |
| 长期记忆 | SessionService 接口后换 Redis / PG；LangGraph checkpointer 可替换 |
| 认证 / 多租户 | Session 与 Request 均已按 user 维度预留字段位（暂不加） |

---

## 8. 错误处理与日志

- 后端：全局异常处理器返回统一 JSON；SSE 流内错误转换为 `error` 事件（流不断，页面不崩）。
- 前端：SSE 解析错误 / 网络错误 → 错误横幅；Tool 失败 → 工具卡片 error 态。
- 日志：标准库 logging，`CREO_LOG_LEVEL` 控制；Runtime 记录 run 生命周期与工具调用。
