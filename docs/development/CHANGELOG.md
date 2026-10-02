# Changelog

记录**用户可感知**的功能变化。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本遵循 SemVer。

## [Unreleased]

### Fixed

- **长对话渲染优化**：MessageItem / MarkdownRenderer / ToolCallCard / Composer 全部 memo 化——流式输出期间仅重渲染正在生成的消息（store 的不可变更新保证未完成消息引用不变），历史越长收益越明显。
- **容错补强**：启动恢复同时覆盖 `pending`（上传已受理但后台任务未及启动）与 `processing` 的中断文档，标记 failed 并提示重试（已完成阶段缓存不重复计费）；KB 登记在线但远端解析栈未配置时，上传接口返回更精确的 503 提示。

- **持久化全量化（重启不丢数据）**：会话列表与对话记忆（含文档定向对话）从内存改为 SQLite 落盘（`data/sessions.sqlite`、`data/checkpoints.sqlite`）；Milvus 连接改为懒式——启动零网络调用，Zilliz 不可达只影响当次向量操作，KB 登记/文件/追踪永远在线；重启时自动把中断的入库任务标记为 failed（可一键重试，已完成阶段走缓存）；Knowledge 页挂载后自动选中第一个知识库（修复"重启后看起来全没了"的观感问题）。测试密闭性同步升级（per-test 数据目录，测试不再触碰真实 `data/`）。

- 修复写在 `backend/.env` 里的 provider 原生 key（如 `OPENAI_API_KEY`）不生效的问题：启动时以绝对路径将 `.env` 载入进程环境（真实环境变量优先），且不再依赖启动时的工作目录；`python-dotenv` 提升为直接依赖。

### Changed

- README 重构为英文主文档（新增知识库完整启动/配置说明与配置项参考），并新增对应的中文版 `README_zh.md`，两版顶部互相链接。
- **LLM 配置全面开放自定义**：新增 `CREO_MODEL_PROVIDER` / `CREO_MODEL_NAME` / `CREO_MODEL_BASE_URL` / `CREO_MODEL_API_KEY` 四个配置项，支持任意 init_chat_model 提供方；OpenAI 兼容端点（DeepSeek、Qwen、Moonshot、Ollama、vLLM…）改 BASE_URL 即可接入。健康检查的 `model` 字段显示当前配置。
- 前端包管理器从 npm 切换为 **pnpm**：`package.json` 以 `packageManager` 锁定 pnpm@12.4.1，lockfile 由 package-lock.json 换为 pnpm-lock.yaml，新增 pnpm-workspace.yaml（构建脚本放行与供应链策略配置），Dockerfile 与 pre-commit 脚本同步更新。

### Added

- **可配置分块策略（ADR-0004 Update 6）**：`CREO_KB_CHUNK_STRATEGY`（pack / title_aware / element）+ `CREO_KB_CHUNK_TITLE_CONTEXT`（标题前置进分块并写入 section 元数据——修复章节标题因过短被丢弃的问题）+ `CREO_KB_CHUNK_OVERLAP`（超长元素滑窗重叠）。入库时生效，改后 reingest 即可应用。
- **Unstructured 官网式元素框选（ADR-0004 Update 5）**：解析请求携带坐标，右栏 PDF 预览新增"元素框选"开关——页面渲染之上叠加按元素类型着色的边框（悬停显示原文），坐标按 layout 尺寸归一化映射；解析缓存升级到 v2（旧文档重新入库一次即可获得坐标）。
- **解析结果与运行链路可视化（ADR-0004 Update 4）**：文档卡片新增"解析结果"按钮——按页分组浏览 Unstructured 元素（类型/页码/关键字过滤/表格 HTML），并可查看该文档已入库的分块原文；会话侧栏与文档对话新增"运行链路"——时间线展示结构化运行事件（消息耗时/字符数、工具调用全量入参与返回、错误），服务端按会话记录（内存环形缓冲，重启清空）。
- **中英双语界面**：零依赖 i18n（Context + 双语字典，`lib/i18n.ts`），语言跟随浏览器、可持久化；头部右上角新增语言切换按钮（与主题切换并列），全部页面文案（导航/对话/知识库/召回测试/弹窗/状态标签）双语覆盖。
- **思考过程可视化（ADR-0002 Update 1）**：推理模型（Qwen/DeepSeek-R1 等）的思考增量以 `thinking_delta` 事件透出，对话中在答案上方显示可折叠的 "Thinking…" 块——思考时自动展开、答案开始后自动收起，可随时点开回看；仅透传模型自带推理，历史回放不含思考内容。
- **知识库封面图格**：左侧文档列表改为"封面即卡片"——第一页缩略图占满卡片，文件名叠加在底部渐变上、状态点左上、悬停右上浮出追踪/重试/删除操作。
- **知识库 v1（ADR-0004）**：支持创建多个知识库（分类）并上传 PDF，后台经 Unstructured Transform API 解析（profile=best，含页码与表格 HTML）并做客户端分块，以 bge-m3 密集向量 + Milvus 服务端 BM25 稀疏向量双通道写入 Zilliz（云上 AUTOINDEX 自适应）；Agent 新增 `search_knowledge_base` 工具做 BM25/Dense 混合检索并引用出处；前端新增 `/knowledge` 管理页（上传、解析状态轮询、失败重试、删除、**pdf.js 内联预览**、**链路追踪时间线**）。付费阶段（解析/向量化）按内容指纹缓存（`data/kb/_cache/`），失败重跑与同内容重复上传零重复计费；删除知识库级联清理登记与追踪数据；KB/文档删除均需二次确认。默认关闭：`CREO_KB_ENABLED=true` 且配齐 `CREO_MILVUS_URI/TOKEN`、`CREO_UNSTRUCTURED_API_KEY`、`CREO_KB_EMBEDDING_*` 后启用；未配齐时 KB 端点返回 503、工具不注册，聊天主链路不受影响。
- **知识库三栏工作台 + 文档定向对话**：Knowledge 页重构为 Dify 风格三栏（文档卡片以第一页作封面、中栏与选中 PDF 对话、右栏连续滚动预览）；定向对话绑定文档级 Agent——检索强制过滤到该 PDF、越界问题拒答，会话记忆按文档隔离。新增 **Recall test** 召回测试页：同一查询三路对比（混合 / 仅密集 / 仅稀疏），为后续 Rerank 决策提供观测依据。
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
