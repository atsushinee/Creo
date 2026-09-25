# AGENTS.md

本文件是 Creo 仓库的**开发总规范**。无论是人类贡献者还是 AI Agent，在修改任何代码之前都必须先阅读并遵守本文件。

---

## 1. 项目阶段与边界

Creo 当前处于 **MVP 阶段**，目标是建立一个**稳定、清晰、可扩展的 Agent 基础框架**，而不是完整的 AI 平台。

**当前实现：**

- React Agent UI
- DeepAgents Backend
- FastAPI
- SSE Streaming
- Agent Session / Agent Event
- Tool Call / Tool Result
- Markdown / Code Block
- Light / Dark Theme
- 基础错误处理 / 日志 / 测试
- 项目治理文档（CHANGELOG / TECHNICAL-NOTES / PITFALLS / ADR）

**明确不做（只预留扩展边界，不得提前实现）：**

- RAG / Knowledge Base / Vector Database
- MCP
- Multi-Agent / Agent-to-Agent
- Workflow Designer
- Long-term Memory
- Authentication / RBAC / Billing / Team
- Web Search / 文件知识库
- 复杂 Artifact 系统

---

## 2. Architecture Rules

### 前端分层

```text
UI (Components / Pages)
 ↓
Hooks (useAgent / useSSE)
 ↓
Services (agentApi)
 ↓
Agent API (FastAPI)
```

- Component 只负责渲染与交互，不直接发请求。
- 网络与 SSE 解析只存在于 `services/` 与 `lib/`。
- 跨组件的 Agent 状态只存在 `stores/agentStore.ts`（zustand）。

### 后端分层

```text
API (FastAPI Routes)
 ↓
Service (session_service)
 ↓
Agent Runtime (agent/runtime.py)
 ↓
DeepAgents (agent/agent.py)
 ↓
LLM / Tools
```

- Route 只做参数校验、组装与 SSE 编码，**不得**塞入 Agent 逻辑。
- Agent Runtime 与 FastAPI 完全解耦（Runtime 不 import fastapi）。
- 存储实现只存在于 Service 层（当前内存实现，未来可换 Redis / PostgreSQL）。

### 禁止的调用模式

```text
React Component → 直接调用 DeepAgents        # ❌ 永远禁止
FastAPI Route → 塞入全部 Agent 逻辑          # ❌ 必须经过 Runtime
Tool → 直接修改 React 状态                   # ❌ Tool 与 UI 通过 Event Protocol 解耦
```

---

## 3. Agent Event Protocol

前端**不能依赖 DeepAgents / LangGraph 内部对象**。前后端之间只有 Creo 自己的 Agent Event（见 `backend/app/models/events.py` 与 `frontend/src/types/agent.ts`，两处必须保持一致）：

```text
run_started / message_start / message_delta / message_end
tool_start / tool_result / error / run_finished
```

- 新增事件类型前先更新 ADR-0002。
- 修改事件字段属于破坏性变更，必须同步前后端与文档。

---

## 4. 每次开发任务开始前（必读清单）

1. `AGENTS.md`
2. `DESIGN.md`
3. `docs/architecture.md`
4. 相关 ADR（`docs/decisions/`）
5. 最近的 `docs/development/CHANGELOG.md`
6. 相关 `docs/development/TECHNICAL-NOTES.md`
7. 相关 `docs/development/PITFALLS.md`

---

## 5. 开发流程

```text
Understand → Plan → Implement → Test → Document → Review
```

禁止：直接改代码 → 能跑 → 结束。

---

## 6. Git Commit 前强制检查

**任何 commit 之前必须依序执行：**

1. `git diff`
2. `git status`
3. 检查测试
4. 检查类型
5. 检查 lint
6. 更新 `docs/development/CHANGELOG.md`
7. 更新 `docs/development/TECHNICAL-NOTES.md`
8. 更新 `docs/development/PITFALLS.md`（没有踩坑也必须记录 "No significant pitfalls encountered."）
9. 必要时新增 / 更新 ADR
10. 再次 `git diff`
11. 最后才能 commit

可以使用 `scripts/pre-commit-check.sh`（见 CONTRIBUTING.md）自动化其中的检查步骤。

---

## 7. Commit Documentation Rule

每次提交后，文档必须能回答：

- **What changed?** —— 改了什么（CHANGELOG.md）
- **Why?** —— 为什么改（TECHNICAL-NOTES.md / ADR）
- **How?** —— 技术上怎么改（TECHNICAL-NOTES.md）
- **Problems?** —— 遇到了什么问题（PITFALLS.md）
- **Solution?** —— 最终怎么解决（PITFALLS.md）
- **Technical Debt?** —— 是否产生新的技术债（TECHNICAL-NOTES.md）

不要为了凑内容虚构问题。

---

## 8. Commit Message

采用 Conventional Commits：

```text
feat: / fix: / refactor: / perf: / docs: / test: / chore: / build: / ci:
```

示例：

```text
feat(agent): add SSE streaming events
fix(ui): prevent duplicate tool result rendering
docs: record DeepAgents integration details
```

---

## 9. Definition of Done

一个任务只有同时满足以下条件才算完成：

```text
Code + Test + Documentation + Review
```

而不是 `Code only`。

---

## 10. 不允许的行为

1. 编造不存在的 API
2. 使用已废弃的 DeepAgents API
3. 为了让代码运行而绕过类型系统
4. 用 `any` 大面积逃避 TypeScript 类型
5. 将业务逻辑全部塞进 React Component
6. 将 Agent 逻辑全部塞进 FastAPI Route
7. Tool 与 UI 强耦合
8. 未验证就升级依赖
9. 修改大量代码却不记录技术细节
10. Git commit 前不更新开发文档
11. 为了"看起来完成"而跳过测试
12. 引入当前阶段不需要的大型依赖
13. 提前实现 RAG / MCP / Multi-Agent
14. 将临时方案伪装成正式架构
15. 删除已有文档来隐藏问题

---

## 11. Dependency Discipline

添加依赖前必须回答：

```text
Why do we need it?
What problem does it solve?
Can existing dependencies solve it?
What is the maintenance cost?
```

新增重要依赖必须在 `docs/development/TECHNICAL-NOTES.md` 中记录。

---

## 12. API Compatibility

所有第三方框架 API（DeepAgents / LangChain / FastAPI / React / Vite / Tailwind）**必须以当前安装版本为准**。

当"文档说 A、安装的包提供 B"时，不要猜。按以下顺序处理：

```text
Inspect installed package
Inspect type definitions
Inspect official documentation
Run minimal reproduction
Record result
```

然后把结论记录到 `docs/development/TECHNICAL-NOTES.md`。

---

## 13. 优先原则

- 优先考虑 **Deterministic Code**：能用普通代码可靠完成的事情，不交给 LLM。
- 只有涉及 Understanding / Reasoning / Planning / Generation / Ambiguous Decision 时才使用 Agent / LLM。
- 先把基础打好，再扩展 Knowledge、RAG、MCP、Multi-Agent 和 Workflow。
