# Creo

> 面向 AI Agent 的现代工作空间。
>
> Creo 来源于拉丁语 **creō** —— 创造、产生、创作、使某物诞生。

[English](README.md) | 中文文档

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

## 功能特性

- 流式对话：DeepAgents 驱动的 Agent（SSE 逐 token 流式输出）
- 会话管理、Tool Call 可视化（running / success / error 三态）
- Markdown 渲染与代码块、Light / Dark 主题
- **知识库 v1**：创建分类知识库、上传 PDF，Agent 以**混合检索——密集向量（bge-m3）+ 稀疏 BM25**（由 Milvus / Zilliz Cloud 服务端完成）引用你的文档

## 界面预览

| 文档对话 · 引用出处 · PDF 预览 | 召回测试——混合 / 仅密集 / 仅稀疏 |
| --- | --- |
| ![文档对话与可点击引用、实时 PDF 预览](imgs/1.png) | ![三路召回对比](imgs/2.png) |

| Agent 回答与工具调用 · PDF 元素框选叠加 | 运行链路——逐事件时间线 |
| --- | --- |
| ![解析元素框选叠加在 PDF 预览上](imgs/3.png) | ![运行链路弹窗：工具入参/返回与耗时](imgs/4.png) |

## 技术栈

| 层 | 技术 |
| --- | --- |
| Frontend | React 19 · TypeScript (strict) · Vite · React Router · Tailwind CSS · shadcn 风格组件 · lucide-react · pnpm |
| Backend | Python 3.12+ · FastAPI · DeepAgents · Pydantic · SSE · uv |
| 知识库 | Unstructured（自托管解析 API）· Milvus / Zilliz Cloud（服务端 BM25 + 密集向量，`pymilvus`）· OpenAI 兼容 Embedding |
| 协议 | Creo Agent Event Protocol（自定义事件协议，前端不依赖 DeepAgents 内部对象） |

## 目录结构

```text
creo/
├── README.md            # 英文文档
├── README_zh.md         # 本文件
├── AGENTS.md            # 开发总规范（AI Agent 与人类贡献者都必读）
├── DESIGN.md            # UI Design System
├── CONTRIBUTING.md      # 开发流程与提交规范
├── scripts/             # 架构边界检查与 pre-commit 辅助脚本
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
- Python ≥ 3.12 与 [uv](https://docs.astral.sh/uv/)
- 一个 LLM API Key（支持任意 provider，OpenAI 兼容端点可自定义 base_url）
- 知识库（可选）：[Zilliz Cloud](https://zilliz.com/cloud) 集群或自托管 Milvus ≥ 2.5、[Unstructured](https://transform.unstructured.io) Transform API Key、Embedding API Key（如 SiliconFlow 上的 `BAAI/bge-m3`）

### 1. 启动后端

```bash
cd backend
cp .env.example .env          # 填写模型与 API key（见下）
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

健康检查：<http://localhost:8000/api/health>（`model` 字段显示当前配置）；API 文档：<http://localhost:8000/docs>

### 2. 配置 LLM

全部在 `backend/.env` 中配置。provider / model / base_url / api_key 均可自定义，支持任何 OpenAI 兼容服务（DeepSeek、Qwen、Moonshot、Ollama、vLLM…）：

```ini
CREO_MODEL_PROVIDER=openai
CREO_MODEL_NAME=gpt-4o-mini
OPENAI_API_KEY=sk-...

# 例：接 DeepSeek —— OpenAI 兼容服务只需改 NAME / BASE_URL / API_KEY
# CREO_MODEL_NAME=deepseek-chat
# CREO_MODEL_BASE_URL=https://api.deepseek.com/v1
# CREO_MODEL_API_KEY=sk-...
```

### 3. 启动前端

```bash
cd frontend
pnpm install
pnpm run dev
```

打开 <http://localhost:5173>（开发模式下 `/api` 已通过 Vite 代理到后端 8000 端口）。

### Docker（可选）

```bash
# 在仓库根目录准备 .env（模型/key 配置，会被 compose 注入 backend）
docker compose up --build
```

打开 <http://localhost:5173>。

## 开发

后端——测试与 lint：

```bash
cd backend
uv run pytest            # 测试
uv run ruff check .      # lint
```

前端——类型检查（strict）、lint、测试：

```bash
cd frontend
pnpm run typecheck       # tsc --noEmit
pnpm run lint            # eslint
pnpm run test            # vitest
pnpm run build           # 生产构建
```

一键 pre-commit 检查（架构边界、设计 token、后端 ruff + pytest、前端 typecheck + lint + test + build）：

```bash
bash scripts/pre-commit-check.sh

# 可选：每次 git commit 自动执行
git config core.hooksPath .githooks
```

## 知识库配置（可选）

知识库默认**关闭**。置 `CREO_KB_ENABLED=true` 并填好下面三个端点；任一缺失——或启动时 Milvus 连不上——KB 保持禁用（端点返回 `503`、检索工具不注册），聊天主链路不受影响。

### 1. Milvus / Zilliz Cloud（向量 + 全文检索）

```ini
CREO_MILVUS_URI=https://in03-xxxx.api-us-west-1.zillizcloud.com   # 集群 endpoint
CREO_MILVUS_TOKEN=                                                # Zilliz Cloud API Key
# 改用自托管 Milvus：CREO_MILVUS_URI=http://localhost:19530
```

- Zilliz Cloud：创建 Dedicated 集群后，从集群页复制 endpoint、从 API Keys 页复制密钥。服务端 BM25 需要 Milvus ≥ 2.5（当前所有 Zilliz Cloud 集群均满足）。
- 每个知识库对应一个 collection（`kb_{slug}_{id}`），首次入库时才懒创建。
- 索引类型自动选择：Zilliz Cloud（dedicated 与 serverless）用 AUTOINDEX；自托管 Milvus 显式 `SPARSE_INVERTED_INDEX` + BM25。

### 2. Unstructured Transform API（PDF 解析）

```ini
CREO_UNSTRUCTURED_API_KEY=          # Unstructured 平台获取的 API Key
# CREO_UNSTRUCTURED_SERVER_URL=https://transform.unstructured.io
# CREO_UNSTRUCTURED_PROFILE=best    # balanced | best | fast（best ≈ hi_res 质量档）
```

解析走 Unstructured 的 Transform API（官方 `unstructured-transform-client` SDK）。Creo 请求结构化 elements（含 1-based 页码与表格 HTML），**分块在客户端完成**：连续元素贪心打包至约 1500 字符，表格独立成块。`best` 为质量档（扫描件可用）；`balanced` 更快更省。

### 3. Embedding（密集向量通道）

```ini
CREO_KB_EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1   # 任何 OpenAI 兼容 /embeddings
CREO_KB_EMBEDDING_API_KEY=
CREO_KB_EMBEDDING_MODEL=BAAI/bge-m3
CREO_KB_EMBEDDING_DIM=1024
```

### 4. 使用流程

1. 打开顶部导航的 **Knowledge** 页 → 新建知识库（即"分类"；每个 KB = 一个本地目录 + 一个 Milvus collection）。
2. 上传 PDF —— 解析、切块、入库在后台执行；文档状态从 `pending → processing → ready / failed` 轮询刷新，失败的文档可一键重试。每个阶段（upload/parse/chunk/embed/index）都会记录——点文档行的**追踪时间线**查看耗时与详情。付费阶段（解析/向量化）按内容指纹缓存于 `backend/data/kb/_cache/`，同文件重复入库不会重复消耗 API 额度。
3. 文档支持**内联预览**（pdf.js 渲染 + 翻页），或到 **Chat** 提问 —— Agent 会调用 `search_knowledge_base` 工具（BM25 + 密集混合检索、RRF 融合），并以 `[1] 文件名 (page N)` 的格式标注出处。检索过程以普通工具卡片形式在 UI 中展示。

### 知识库注意事项

- Embedding 模型、维度与中文分析器（`CREO_KB_ANALYZER=chinese`，jieba 系）在 **collection 创建时固定**；要更换需删除知识库重新上传入库。
- 上传原件与 SQLite 登记库位于 `backend/data/kb/`（已 git-ignore）。
- 后端重启可能让进行中的文档停在 `processing`——用页面上的重试按钮重新入库（幂等：先删旧向量再插入）。

## 配置项参考

所有变量使用 `CREO_` 前缀，配置于 `backend/.env`（带注释的完整清单见 `.env.example`）。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `CREO_MODEL_PROVIDER` | `openai` | 任意 init_chat_model 支持的 provider |
| `CREO_MODEL_NAME` | `gpt-4o-mini` | 模型名 |
| `CREO_MODEL_API_KEY` | — | 可选；缺省回落 provider 原生环境变量 |
| `CREO_MODEL_BASE_URL` | — | 可选；OpenAI 兼容端点地址 |
| `CREO_AGENT_INSTRUCTIONS` | 内置 | Agent 系统提示词 |
| `CREO_CORS_ORIGINS` | localhost:5173 | 逗号分隔的允许来源 |
| `CREO_LOG_LEVEL` | `INFO` | 标准库日志级别 |
| `CREO_KB_ENABLED` | `false` | 知识库总开关 |
| `CREO_MILVUS_URI` | — | Zilliz Cloud endpoint 或 `http://host:19530` |
| `CREO_MILVUS_TOKEN` | — | Zilliz Cloud API Key（自托管无认证时留空） |
| `CREO_UNSTRUCTURED_API_KEY` | — | Unstructured Transform API Key（知识库必填） |
| `CREO_UNSTRUCTURED_SERVER_URL` | `https://transform.unstructured.io` | 其他部署时覆盖；结尾的 `/api/v2` 会被自动剥离（旧变量名 `CREO_UNSTRUCTURED_API_URL` 仍兼容） |
| `CREO_UNSTRUCTURED_PROFILE` | `best` | 解析档位：`balanced` \| `best` \| `fast` |
| `CREO_KB_EMBEDDING_BASE_URL` | — | OpenAI 兼容 `/embeddings` 地址 |
| `CREO_KB_EMBEDDING_API_KEY` | — | Bearer Token |
| `CREO_KB_EMBEDDING_MODEL` | `BAAI/bge-m3` | Embedding 模型 |
| `CREO_KB_EMBEDDING_DIM` | `1024` | 向量维度（必须与模型一致） |
| `CREO_KB_ANALYZER` | `chinese` | BM25 分析器；`chinese`/`english`/`standard` 或 JSON analyzer_params |
| `CREO_KB_CHUNK_MAX_CHARACTERS` | `1500` | 单块最大字符数 |
| `CREO_KB_CHUNK_STRATEGY` | `pack` | 分块策略：`pack`（贪心打包）\| `title_aware`（标题强制分节）\| `element`（一元素一块）。入库时生效——改后需重新入库 |
| `CREO_KB_CHUNK_TITLE_CONTEXT` | `true` | 将最近的标题前置到每个分块（并写入 `section` 元数据） |
| `CREO_KB_CHUNK_OVERLAP` | `0` | 超长元素滑窗切分的重叠字符数 |
| `CREO_KB_DATA_DIR` | `backend/data/kb` | 上传文件 + SQLite 登记库 |
| `CREO_KB_UPLOAD_MAX_MB` | `50` | 单文件上传上限 |
| `CREO_KB_SEARCH_TOP_K` | `5` | 检索工具默认 top_k |

## 文档索引

| 文档 | 内容 |
| --- | --- |
| [AGENTS.md](AGENTS.md) | 开发总规范：架构规则、禁止行为、提交纪律 |
| [DESIGN.md](DESIGN.md) | Creo Design Language：色彩、排版、组件规范 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 开发流程、Conventional Commits、Pre-commit Checklist |
| [docs/architecture.md](docs/architecture.md) | 系统架构与模块职责 |
| [docs/decisions/](docs/decisions/) | ADR：项目架构、Agent Event Protocol、SSE Streaming、知识库混合检索 |
| [docs/development/CHANGELOG.md](docs/development/CHANGELOG.md) | 用户可感知的功能变化 |
| [docs/development/TECHNICAL-NOTES.md](docs/development/TECHNICAL-NOTES.md) | 技术实现细节与决策原因 |
| [docs/development/PITFALLS.md](docs/development/PITFALLS.md) | 踩坑记录 |
| [docs/milestones/](docs/milestones/) | 验收标准与状态（MVP、KB v1） |

## 当前状态

已实现：React Agent UI、DeepAgents Backend、SSE Streaming、Agent Session、Tool Call 可视化、Markdown / Code Block、Light / Dark Theme、基础错误处理、日志、测试、完整的项目治理文档，以及**知识库 v1**（PDF 上传 → Unstructured 解析 → BM25 + Dense 混合入库 Milvus/Zilliz → Agent 检索工具）。

尚未实现（只预留扩展边界）：RAG 深水区（多格式解析、Rerank、GraphRAG）、MCP、Multi-Agent、Workflow、长期记忆、认证。

## Roadmap

每个阶段都落在稳定基础上再进入下一阶段——范围纪律见 [AGENTS.md](AGENTS.md)，以下事项**不会**提前实现。

- [x] MVP —— Agent 对话、SSE 流式、会话管理、Tool 可视化、Markdown / 代码块、主题、治理文档
- [x] 知识库 v1 —— PDF 上传、Unstructured 解析、混合检索（BM25 + Dense）、Agent 引用作答
- [ ] 知识库 v2 —— 多格式解析（Office / HTML / 图片）、Rerank、GraphRAG、增量同步
- [ ] MCP（Model Context Protocol）支持
- [ ] Multi-Agent / Agent-to-Agent
- [ ] Workflow 设计器
- [ ] 长期记忆
- [ ] 认证 / RBAC

## License

暂未确定，MVP 阶段保留所有权利。
