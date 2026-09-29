# Changelog

记录**用户可感知**的功能变化。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本遵循 SemVer。

## [Unreleased]

### Fixed

- 修复写在 `backend/.env` 里的 provider 原生 key（如 `OPENAI_API_KEY`）不生效的问题：启动时以绝对路径将 `.env` 载入进程环境（真实环境变量优先），且不再依赖启动时的工作目录；`python-dotenv` 提升为直接依赖。

### Changed

- README 重构为英文主文档（新增知识库完整启动/配置说明与配置项参考），并新增对应的中文版 `README_zh.md`，两版顶部互相链接。
- **LLM 配置全面开放自定义**：新增 `CREO_MODEL_PROVIDER` / `CREO_MODEL_NAME` / `CREO_MODEL_BASE_URL` / `CREO_MODEL_API_KEY` 四个配置项，支持任意 init_chat_model 提供方；OpenAI 兼容端点（DeepSeek、Qwen、Moonshot、Ollama、vLLM…）改 BASE_URL 即可接入。健康检查的 `model` 字段显示当前配置。
- 前端包管理器从 npm 切换为 **pnpm**：`package.json` 以 `packageManager` 锁定 pnpm@12.4.1，lockfile 由 package-lock.json 换为 pnpm-lock.yaml，新增 pnpm-workspace.yaml（构建脚本放行与供应链策略配置），Dockerfile 与 pre-commit 脚本同步更新。

### Added

- **知识库 v1（ADR-0004）**：支持创建多个知识库（分类）并上传 PDF，后台经 Unstructured Transform API 解析（profile=best，含页码与表格 HTML）并做客户端分块，以 bge-m3 密集向量 + Milvus 服务端 BM25 稀疏向量双通道写入 Zilliz（云上 AUTOINDEX 自适应）；Agent 新增 `search_knowledge_base` 工具做 BM25/Dense 混合检索并引用出处；前端新增 `/knowledge` 管理页（上传、解析状态轮询、失败重试、删除、**pdf.js 内联预览**、**链路追踪时间线**）。付费阶段（解析/向量化）按内容指纹缓存（`data/kb/_cache/`），失败重跑与同内容重复上传零重复计费；删除知识库级联清理登记与追踪数据；KB/文档删除均需二次确认。默认关闭：`CREO_KB_ENABLED=true` 且配齐 `CREO_MILVUS_URI/TOKEN`、`CREO_UNSTRUCTURED_API_KEY`、`CREO_KB_EMBEDDING_*` 后启用；未配齐时 KB 端点返回 503、工具不注册，聊天主链路不受影响。
- 新增直接依赖：`unstructured-transform-client`（Transform API 官方 SDK）、`pymilvus`（仅 `services/kb_vector_store.py` 可 import，边界脚本强制）、`httpx`（自 dev 组提升为运行时依赖）、`python-multipart`（multipart 上传）；前端新增 `pdfjs-dist`（PDF 预览）。
- **LLM 配置开放自定义**（同上 Changed）：`.env.example` 提供 DeepSeek / Ollama / Anthropic 等完整示例。
- 仓库边界与设计 token 自动检查脚本 `scripts/check-boundaries.mjs`（借鉴 OpenBitFun 的 check-scripts 文化），强制 AGENTS.md 分层边界与 DESIGN.md 颜色纪律，已接入 pre-commit 首道检查。
- Agent 会话基础链路：React Agent UI → SSE → FastAPI → DeepAgents → LLM → Tools → Result，全程流式。
- `POST /api/chat`：SSE 流式返回 Creo Agent Event（run_started / message_start / message_delta / message_end / tool_start / tool_result / error / run_finished）。
- 会话管理：会话列表、历史消息读取、删除（内存存储）。
- Demo Tools：`calculator`（AST 安全算术求值）、`get_current_time`。
- Agent UI：会话侧栏、流式助手输出、Tool Call 卡片（running / success / error 三态、可折叠查看 Arguments 与 Result）、Thinking 状态行、错误横幅、空状态建议。
- Markdown 渲染（GFM）与代码块（语言标签 + 复制按钮 + 低饱和语法高亮）。
- Light / Dark 主题（跟随系统，可手动切换并持久化）。
- 健康检查 `GET /api/health`。
- 项目治理文档：AGENTS.md / DESIGN.md / CONTRIBUTING.md / architecture.md / ADR-0001~0003 / CHANGELOG / TECHNICAL-NOTES / PITFALLS / MVP 里程碑。
- `scripts/pre-commit-check.sh` 提交前自动检查脚本与可选 git hook。
- docker-compose 与前后端 Dockerfile（本地编排演示）。
