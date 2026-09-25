# ADR-0001: Project Architecture

## Status

Accepted（2026-09-25）

## Context

Creo 要从零建立一个 AI Agent Workspace。MVP 阶段的核心诉求：

1. 稳定的 Agent Runtime（流式、可扩展）
2. 清晰的 Event Protocol（前端不被任何 Agent 框架绑架）
3. 优秀的 Agent UI（克制、专业、工具调用一等公民）
4. 可维护的工程结构（分层明确、文档持续积累）

需要在「快速起步」与「长期架构」之间取得平衡，避免过早引入平台级复杂度（认证、数据库、队列、向量库）。

## Decision

- **前后端分离 monorepo**：`frontend/` + `backend/`，独立依赖与工具链。
- **前端**：React 19 + TypeScript (strict) + Vite + React Router + Tailwind CSS + shadcn 风格组件。**不用 Next.js**（Creo 是工具型 SPA，无 SSR/SEO 需求，Vite 更简单可控）。
- **后端**：Python 3.12+ / FastAPI / **DeepAgents**（LangGraph 之上）作为 Agent Runtime，uv 管理依赖。
- **分层**：
  - Frontend：`UI → Hooks → Services → Agent API`
  - Backend：`API → Service → Agent Runtime → DeepAgents → LLM/Tools`
- **会话**：MVP 用内存（SessionService 接口隔离 + LangGraph MemorySaver checkpointer），不引入数据库。
- **传输**：SSE（见 ADR-0003）。
- **协议**：自定义 Agent Event Protocol（见 ADR-0002），DeepAgents 内部对象不出后端。

## Alternatives

| 方案 | 不选原因 |
| --- | --- |
| Next.js 全栈 | SSR/路由/部署复杂度对 Agent 工具型 UI 无收益；团队要在 Vite 生态内保持轻快 |
| 直接用 LangGraph 裸建 Agent | DeepAgents 内置规划（todo）、文件系统、子代理等 Agent 基建，长期演进成本低；本阶段只用到其最小面 |
| 把 DeepAgents 事件直接透传给前端 | 前端将绑定 LangGraph 对象形状，框架升级即破坏 UI；违背 Event Protocol 边界 |
| 一开始就上 PostgreSQL / Redis | MVP 无持久化需求；接口隔离后随时可替换（记录在 architecture.md） |

## Consequences

- 优点：链路短、心智负担低、每一层都可独立替换（存储、Runtime、UI）。
- 代价：DeepAgents 与前端之间需要一层显式的事件适配器（runtime.py），多写一些转换代码 —— 这是刻意购买的正确性。
- 技术债：内存存储重启即失；checkpointer 为进程内实现。已知且接受（MVP 范围内）。
