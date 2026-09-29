# ADR-0002: Agent Event Protocol

## Status

Accepted（2026-09-25）；Update 1（2026-09-30）：新增 `thinking_delta`

## Update 1（2026-09-30）：thinking_delta 事件

推理模型（DashScope/Qwen 的 `reasoning_content`、Anthropic 式 thinking 内容块）的思考文本需要透出到 UI。新增事件：

```text
thinking_delta   { content: string }  思考增量
```

约束与决策：

- 运行时只**透传**模型自带的推理增量（`additional_kwargs.reasoning_content` / thinking 块），不生成、不解释、不参与最终答案；历史回放（`get_history`）不含思考内容——UI 历史只渲染答案与工具。
- 事件不带 messageId：前端附加到当前流式中的助手消息首部（无流式消息则创建占位消息）；`message_start/message_end` 生命周期不变。
- 兼容性：非推理模型不产生该事件，前端零影响。
- 前后端镜像同步（`models/events.py` / `types/agent.ts`）。

---

（以下为原文档）

## Context

DeepAgents（LangGraph）的原始流由多种形状组成：AIMessageChunk（token 增量、tool_call_chunks）、ToolMessage、节点状态更新（updates）等。如果把它们直接透传给前端：

- React 需要理解 LangChain/LangGraph 的对象模型（`content` 可能是 str 或 block 列表、tool_call_chunks 的部分 JSON 等）；
- 框架升级（deepagents 0.x → 1.x）会直接破坏 UI；
- 无法做协议级测试（前后端各自无法独立验收）。

## Decision

建立 **Creo 自己的 Agent Event Protocol**。后端 Agent Runtime 是唯一翻译层，前端只认识以下事件（`type` 判别联合，JSON over SSE）：

```typescript
type AgentEvent =
  | { type: "run_started";  runId: string }
  | { type: "message_start";  messageId: string }
  | { type: "message_delta";  messageId: string; content: string }
  | { type: "message_end";    messageId: string }
  | { type: "tool_start";     toolCallId: string; toolName: string; args: unknown }
  | { type: "tool_result";    toolCallId: string; result: unknown; isError?: boolean }
  | { type: "error";          message: string }
  | { type: "run_finished";   runId: string };
```

约定：

1. `tool_start.args` 是**完整解析后的 JSON 对象**（不是部分 JSON 字符串）；在 updates 流中拿到完整 tool_calls 后才发出。
2. `tool_result.isError` 标记工具失败（如 calculator 表达式非法）。UI 据此显示 error 态。
3. 一条 `run` 内允许多段 message（工具调用会把助手输出切成多段文本）。
4. 事件顺序保证：`run_started → (message_start → message_delta* → message_end | tool_start → tool_result)* → run_finished`。
5. 单一事实来源：后端 `backend/app/models/events.py` 与前端 `frontend/src/types/agent.ts` 必须一致；以 events.py 为准。

### 预留扩展（当前不实现）

`approval_required` / `state_update` / `artifact_created` / `artifact_updated` / `source_added` / `agent_status`

新增事件必须先更新本 ADR，再同步实现前后端。

## Alternatives

| 方案 | 不选原因 |
| --- | --- |
| 透传 LangGraph 原始事件 | 前端绑定框架对象形状；无法协议测试 |
| 采用开源通用协议（如 AG-UI） | 当前阶段引协议级依赖收益低；Creo 事件更小更可控，未来需要时可做适配层转换 |
| WebSocket 双向流 | 本阶段 Agent → UI 单向为主（见 ADR-0003），双向是过度设计 |

## Consequences

- 每加一种后端流形状（如 subgraph 事件），只在 runtime.py 适配；UI 不动。
- 前端 store 的 `applyAgentEvent` 成为可单测的纯函数。
- 协议演进需要纪律：改事件必须同步 events.py / types/agent.ts / 本 ADR。
