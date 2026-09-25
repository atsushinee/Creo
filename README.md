# Creo

> 面向 AI Agent 的现代工作空间。
>
> Creo 来源于拉丁语 **creō** —— 创造、产生、创作、使某物诞生。

Creo 当前处于 **MVP 阶段**：不追求功能数量，而是先建立一个稳定、清晰、可扩展的 Agent 基础框架。所有未来的能力（Knowledge / RAG / MCP / Multi-Agent / Workflow）都将在这个基础上演进。

## 核心链路

```text
User
  ↓
React Agent UI
  ↓
SSE / HTTP
  ↓
FastAPI
  ↓
DeepAgents
  ↓
LLM
  ↓
Tools
  ↓
Result
```

## 技术栈

| 层 | 技术 |
| --- | --- |
| Frontend | React 19 · TypeScript (strict) · Vite · React Router · Tailwind CSS · shadcn 风格组件 · lucide-react · pnpm |
| Backend | Python 3.12+ · FastAPI · DeepAgents · Pydantic · SSE · uv |
| 协议 | Creo Agent Event Protocol（自定义事件协议，前端不依赖 DeepAgents 内部对象） |

## 目录结构

```text
creo/
├── README.md            # 本文件
├── AGENTS.md            # 开发总规范（AI Agent 与人类贡献者都必读）
├── DESIGN.md            # UI Design System
├── CONTRIBUTING.md      # 开发流程与提交规范
├── docs/
│   ├── architecture.md  # 架构说明
│   ├── decisions/       # ADR（架构决策记录）
│   ├── development/     # CHANGELOG / TECHNICAL-NOTES / PITFALLS
│   └── milestones/      # MVP 验收标准与状态
├── frontend/            # React Agent UI
└── backend/             # FastAPI + DeepAgents Runtime
```

## 快速开始

### 前置条件

- Node.js ≥ 20.19（推荐 22）+ **pnpm 12**（`corepack enable` 或 `npm i -g pnpm`）
- Python ≥ 3.12
- [uv](https://docs.astral.sh/uv/)
- 一个 LLM API Key（默认使用 OpenAI 兼容模型）

### 后端

```bash
cd backend
cp .env.example .env          # 填入 OPENAI_API_KEY（或其他 provider 的 key）
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

健康检查：<http://localhost:8000/api/health>，API 文档：<http://localhost:8000/docs>

### 前端

```bash
cd frontend
pnpm install
pnpm run dev
```

打开 <http://localhost:5173>（开发模式下 `/api` 已通过 Vite 代理到后端 8000 端口）。

### Docker（可选）

```bash
# 在仓库根目录准备 .env：OPENAI_API_KEY=sk-...（会被 compose 注入 backend）
docker compose up --build
```

打开 <http://localhost:5173>。

## 文档索引

| 文档 | 内容 |
| --- | --- |
| [AGENTS.md](AGENTS.md) | 开发总规范：架构规则、禁止行为、提交纪律 |
| [DESIGN.md](DESIGN.md) | Creo Design Language：色彩、排版、组件规范 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 开发流程、Conventional Commits、Pre-commit Checklist |
| [docs/architecture.md](docs/architecture.md) | 系统架构与模块职责 |
| [docs/decisions/](docs/decisions/) | ADR：项目架构、Agent Event Protocol、SSE Streaming |
| [docs/development/CHANGELOG.md](docs/development/CHANGELOG.md) | 用户可感知的功能变化 |
| [docs/development/TECHNICAL-NOTES.md](docs/development/TECHNICAL-NOTES.md) | 技术实现细节与决策原因 |
| [docs/development/PITFALLS.md](docs/development/PITFALLS.md) | 踩坑记录 |
| [docs/milestones/MVP.md](docs/milestones/MVP.md) | MVP 验收标准 |

## 当前状态

MVP 已实现：React Agent UI、DeepAgents Backend、SSE Streaming、Agent Session、Tool Call 可视化、Markdown / Code Block、Light / Dark Theme、基础错误处理、日志、测试与完整的项目治理文档。

尚未实现（只预留扩展边界）：RAG、Knowledge Base、MCP、Multi-Agent、Workflow、长期记忆、认证。

## License

暂未确定，MVP 阶段保留所有权利。
