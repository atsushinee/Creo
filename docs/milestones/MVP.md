# Milestone: MVP

> 目标：一个稳定、清晰、可扩展的 Agent 基础框架。

## 验收标准（Acceptance）

> 自动化验证：以下 Case 1–3 均有对应的集成测试（`backend/tests/test_runtime.py`，使用 ScriptedChatModel 驱动真实 DeepAgents 图，无需 API key）。带 🔑 的条目需要用真实 API key 手工跑一遍确认。

### Case 1 — 纯对话流式

输入：`你好`

- [x] Agent 以 SSE 流式返回文本（逐 token 增量，非一次性返回）。
- [ ] 🔑 用真实 LLM 手工确认一次。

### Case 2 — 工具调用全链路

输入：`计算 123 * 456`

- [x] 流程：Agent → calculator → Tool Result → Agent → `56088`，全程流式（test_full_tool_call_flow）。
- [x] UI 显示工具卡片：`running` → `success`，默认折叠，可展开查看 Arguments 与 Result（组件实现 + store 单测）。
- [ ] 🔑 用真实 LLM 手工确认一次端到端。

### Case 3 — 工具失败不崩溃

构造 calculator 出错（如 `1/0`）：

- [x] 工具卡片显示 `error` 态与错误信息（test_tool_error_is_reported_not_raised + ToolErrorMiddleware）。
- [x] 页面不崩溃，Agent 可继续对话（run 正常 run_finished）。

### 横向要求

- [x] Light / Dark 主题切换并持久化。
- [x] 会话侧栏：新建会话、切换会话并恢复历史、删除会话（API 级测试覆盖）。
- [x] Stop 按钮可中断流（AbortController + 后端 GeneratorExit 安全退出）。
- [x] 后端测试 / lint 通过（27 passed / ruff clean）；前端 typecheck / lint / test / build 通过（13 passed）。
- [x] 仓库无 `.env` / API key 等敏感信息（提交前 git status/diff 复查）。

## 范围外（不做）

RAG、Knowledge Base、向量库、MCP、Multi-Agent、Workflow Designer、长期记忆、认证、RBAC、Billing、Team、Web Search、文件知识库、复杂 Artifact 系统。

## 状态

- 实现状态：见 `docs/development/CHANGELOG.md` 的 `[Unreleased]`。
