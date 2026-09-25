# ADR-0003: SSE Streaming (POST + fetch ReadableStream)

## Status

Accepted（2026-09-25）

## Context

Agent → UI 的主要数据方向是**单向流式**（token 增量、工具开始/结束、状态）。需要选择传输方式，并保证真正逐 token 流式，禁止「等 Agent 跑完一次性返回」。

## Decision

- 传输用 **SSE**（`text/event-stream`），但通过 `fetch` + `ReadableStream` 消费，而不是 `EventSource`。
- 请求是 **POST**（`POST /api/chat`，body 为 JSON）：Agent 调用需要携带完整上下文（session_id + message），GET + query string 不合适。
- SSE 帧格式：

```text
event: message_delta
data: {"type":"message_delta","messageId":"...","content":"..."}

```

- 后端用 FastAPI `StreamingResponse` 手写帧编码（不引入 sse-starlette：编码本身只有几行，依赖纪律优先）。
- 前端在 `src/lib/sse.ts` 实现纯函数帧解析器（跨 chunk 边界缓冲），`useSSE` hook 管理请求生命周期与 AbortController（Stop 按钮）。

## Alternatives

| 方案 | 不选原因 |
| --- | --- |
| `EventSource` | 只支持 GET，无法携带 JSON body |
| WebSocket | 双向、有状态、需要心跳/重连/协议升级；Agent → UI 单向流用不上，MVP 过度设计 |
| 轮询 | 延迟高、浪费请求，与「真正流式」的目标冲突 |
| sse-starlette 库 | 编码逻辑极小，标准库 + StreamingResponse 足够；减少一个依赖 |

## Consequences

- 断线处理需自己做：fetch 流中断时前端感知异常并显示错误横幅（EventSource 有自动重连，fetch 没有 —— MVP 接受，未来可加 `Last-Event-ID` 式恢复）。
- 代理/缓冲注意：响应需带 `Cache-Control: no-cache`、`X-Accel-Buffering: no`，Vite dev proxy 与 uvicorn 均为流式透传（已验证）。
- 事件用 `event:` + `data:` 两行帧，解析器按空行分帧；未来加 `id:` 字段可无缝升级断点续传。
