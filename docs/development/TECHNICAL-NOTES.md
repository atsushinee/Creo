# Technical Notes

记录技术实现细节：为什么这样设计、放弃了什么方案、API 版本差异、关键实现细节、性能与兼容性问题。新条目加在最上面。

---

## 2026-10-12

### 引用跳转（citation → PDF 页码定位）

- **映射来源**：知识检索工具的返回是纯文本（`"[1] filename (page 3)\n<chunk>\n\n[2] …"`，见 `knowledge_tools.py`），前端不需要新增事件字段——`MessageItem.parseCitationPages` 直接用正则 `/^\[(\d+)\][^\n]*?\(page\s*(\d+)/gim` 从最近一次成功的 `search_knowledge_base` / `search_document` 结果解析出"引用编号 → 页码"。文本块按 part 匹配：每个 text part 向前找最近的检索工具结果，多轮多工具场景下引用归属正确。
- **格式容错**：模型并不总是按工具要求的 `[N]` 格式输出，实测会出现 `[1, page 3]`（页码写进方括号）。前端正则兼容两种变体：`[N]`（页码从工具结果解析）与 `[N, page P]`（内嵌页码直通，优先于工具结果解析）；两种情况标记都改写为转义方括号的链接（`\[N\](cite://N[/P])`），显示保持原样，fenced code 内不改写。
- **渲染改写**：`MarkdownRenderer` 仅在传入 `onCitation` 时把独立 `[N]` 标记改写为 `[N](cite://N)` 链接（正则带 `(?<!\])` / `(?!\()` 防御：不吃 reference-style 链接与真实链接），自定义 `a` 组件拦截 `cite://` href 渲染为按钮并上报编号；**fenced code block 内不改写**（按 ``` 分段跳过）。注意：react-markdown 的 `defaultUrlTransform` 会把非标准协议消毒为空 href，必须同时传自定义 `urlTransform` 放行 `cite://`（见 PITFALLS 2026-10-12）。主聊天界面不传 handler，引用保持纯文本，零行为变化。
- **命令式桥接**：`PdfViewer` 改 `forwardRef + useImperativeHandle` 暴露 `scrollToPage`（复用内部翻页/页码同步逻辑）；`KnowledgePage` 持 ref，`handleCitationClick` 用 `useCallback` 稳定引用穿过 DocChatPanel → ChatMessages → MessageItem（memo 组件的 props 稳定性）。
- **已知边界**：chunk 是打包生成的，未存 chunk↔element 坐标区间，所以点击引用**跳到页**而非高亮具体元素框；元素级定位需要入库时额外落 chunk→element 映射（留作后续）。

---

## 2026-10-03

### Unstructured 坐标可视化 + 解析缓存 v2

- **include 值实测**：`coordinates` 与 `table_html` 可同时请求（此前只敢单独用）；坐标形状为 `metadata.coordinates = {points: [[x,y]…], system: {layout_width, layout_height, …}}`——前端按 layout 尺寸归一化映射到 pdf.js 画布（DPI 无关），并对 `width/height` 拼写做了防御。
- **解析缓存 v2**：文件名加 `-v2` 版本戳（`{sha16}-{profile}-v2.json`），升级请求后旧的无坐标条目自动失效；`save_parse` 会清理同文档同 profile 的旧格式文件。**已有文档需要一次 reingest 才能拿到坐标**（缓存 miss → 重解析，计费一次）。
- **预览叠加层**：SVG 覆盖在 pdf.js canvas 之上（画布像素尺寸 = viewport 尺寸，坐标比例直接映射）；类型→描边色映射设计 token（CSS 变量用于 SVG 属性，未违反 hex 禁令）；`<title>` 提供悬停原文；rect `pointer-events: auto` + svg `none` 保证缩放滚动不受影响。
- **React 细节**：查看器弹窗的挂载期加载必须走 `.then` 回调 setState（`react-hooks/set-state-in-effect` 对"effect 内调用含 setState 的 useCallback"一律告警，即使函数体先 await）——与 useKnowledgeBase 挂载模式保持一致。

---

## 2026-09-30（续）

### 长对话渲染优化 + 评审补强（容错清单）

**memo 化的前提**：`agentStore.applyAgentEvent` 的更新是不可变且按消息粒度的——`mapMessage` 只替换被触及消息的对象，未触及消息引用不变。因此 `memo` 包一层即可让流式期间只重渲染在流的消息：`MessageItem`（省掉全部历史消息的 Markdown 重解析，这是长对话最大开销）、`MarkdownRenderer`、`ToolCallCard`、`Composer`（props 为布尔值 + 稳定回调）。`useDocChat` 的 `applyDocEvent` 同样保持消息粒度不可变 ✓。`React.memo` 未覆盖 AppSidebar/AppHeader——ChatPage 传给它们的回调（如内联箭头函数、依赖 `messagesBySession` 的 selectSession）每个 token 都变，memo 无效；侧栏/头部本身渲染很轻，暂不为此增加回调稳定化管道。

**评审发现的容错缺口（已修）**：启动恢复原先只标记 `processing`——若进程在"上传响应已返回、后台任务未及启动"的窗口被杀，文档会永远停在 `pending`、前端无限轮询。现恢复覆盖 `pending + processing`。另把"登记在线但解析栈未配置"场景的上传 503 文案精确化（与"整个 KB 禁用"区分）。

---

## 2026-09-30

### 持久化全量化（重启不丢任何数据）+ KB 栈与远端服务解耦

用户反馈"重启后上传的 PDF 都没了"。诊断：**数据其实都在**（kb.sqlite、原件、追踪、缓存全部落盘），真因是两个——① 前端 `currentKbId` 初始为 null 且不自动选中，重启后列表加载了但上传按钮被 `!currentKb` 禁用、文档网格不渲染，观感即"全没了"；② KB 栈存活与 Zilliz 启动时是否连得上耦合（MilvusClient 构造即拨号，连不上→整个栈禁用→登记接口 503）。修复：

- **前端**：挂载加载 KB 列表后自动选中第一个并拉取其文档（仅挂载时执行，不覆盖用户后续操作）。
- **Milvus 懒连接**：`MilvusVectorStore.client` property 首次使用才连（双检锁），构造零网络；连接失败只让当次操作抛 `MilvusException`（实测类型），下次调用重试，登记/文件/追踪永远在线。构造函数支持注入 client 供测试。
- **登记与远端解耦**：`_build_knowledge_stack` 先建 SqliteKnowledgeService + 启动恢复，缺远端配置只禁用"入库/检索工具"，登记接口照常。
- **会话持久化**：`SqliteSessionService`（stdlib sqlite3，`data/sessions.sqlite`）替换内存实现，接口不变。
- **对话记忆持久化**：`langgraph-checkpoint-sqlite` 的 `AsyncSqliteSaver`（`data/checkpoints.sqlite`）替换 MemorySaver，全局聊天与所有 doc-chat scope 共享一个 saver（线程按 session_id 隔离，`docchat-{docId}` 前缀天然不冲突）。lifespan 用 `async with open_checkpointer(...)` 管理 lifecycle；langgraph 导入留在 agent 层（`app/agent/checkpointer.py`）以通过边界脚本。
- **启动恢复**：`fail_interrupted_ingestions()` 把重启时卡在 processing 的文档标记为 failed（提示可重试，已完成阶段走缓存），前端不再无限轮询。
- **测试密闭升级**：conftest 的 hermetic fixture 现在同时重定向 `data_dir`/`kb_data_dir` 到 per-test tmp——曾抓到 test_api 把测试会话写进真实 sessions.sqlite（已清理）。持久化相关测试见 `tests/test_persistence.py`。

依赖新增：`langgraph-checkpoint-sqlite`、`aiosqlite`。

---

## 2026-09-29（晚）

### 解析后端切换：自托管 Partition Endpoint → Unstructured Transform API（SDK 0.18.21 实测）

用户提供的是 Transform API（transform.unstructured.io）与官方 SDK，按 AGENTS.md §12 对安装版本逐项实测：

- **`ParseResult.elements` 恒返回**（必填字段，"canonical document"）；`markdown` 仅在请求 markdown 表示时有值。我们直接消费 elements，不依赖 markdown。
- **分块搬到客户端**：v2 无 chunking 参数。`pack_elements()`：连续叙事元素贪心打包（软限制 = 80% max_chars）、Table 独立成块（text_as_html 优先）、单元素超长硬切、<20 字符丢弃；块页码取首个元素的 `page_number`。
- `Element.metadata.page_number`（1-based）默认返回。表格 HTML 的请求投影叫 **`table_html`**（include 合法值仅 `coordinates` / `table_html`，且必须 `output="elements"`，默认 markdown 下 include 会 400），但**响应字段仍叫 `metadata.text_as_html`**——请求/响应命名错位，两次 400 实测确认。
- **profile 取代 strategy**：`balanced | best | fast`（best ≈ 旧 hi_res 质量档）。OCR 语言/策略参数在 v2 不存在，对应配置项删除。
- `parse.run(wait_seconds=None)` → 不发 Prefer 头，**同步阻塞**到任务完成（跑在 BackgroundTasks 线程池，不影响事件循环）。
- **SDK 的 `server_url` 不能带 `/api/v2`**：SDK 自行拼接 `/api/v2/...` 路径。适配层 `_normalize_server_url` 剥离该后缀；`Settings` 用 `AliasChoices` 兼容旧变量名 `CREO_UNSTRUCTURED_API_URL`。
- `TransformClient` 构造为 keyword-only（`api_key/server_url/timeout_seconds/retries: RetryConfig`），缺 key 构造即抛——lifespan 的缺配置检查先行拦截。
- 内置重试：GET/DELETE 对任意瞬时失败重试；写操作只在"确定未到达服务端"时重试（连接拒绝/DNS），读超时与 5xx 不重试——我们在管线层有自己的失败兜底（文档状态机）。

**Zilliz serverless（us-west-1）实测**：DDL（drop/create_collection）偶发 `DEADLINE_EXCEEDED: The upstream server is timing out`（插入/检索反而稳定）。对策：`MilvusVectorStore` 所有操作显式 `timeout=60s`；冒烟脚本清理 3 次重试 + 启动时自愈清残留 `kb_smoke_*`（serverless 超时后服务端往往已执行，重试时 has_collection 为 False 会自然跳过）。

**冒烟测试脚本**：`backend/scripts/smoke_kb.py`（不属 pytest，手动运行）。解析与 embedding 两个付费阶段经 `PipelineCache`（`data/kb/_cache/`，内容寻址）缓存，与应用共享——重跑/失败重试零重复计费；控制台输出 tee 到 `data/smoke/run.log`。真实链路结论：54 页《公司章程》profile=best 解析 220s / 842 elements → 33 chunks → bge-m3 33×1024 → serverless 写入/检索/删除全部正常，RRF 分数量级符合预期（~1/61）；**应用级链路**（真实 IngestionService + trace + KbSearchService）全部缓存命中下 8.0s 完成，查询 embedding 为唯一 API 消耗。

**pdfjs-dist 6.3.289 勘察（前端预览）**：`PDFDocumentProxy.destroy()` 已移除——销毁走 `PDFDocumentLoadingTask.destroy()`（持有 loadingTask 引用清理）；`page.render()` 必须传 `canvas`（`canvasContext` 参数已不再是唯一入口）；worker 经 `pdfjs-dist/build/pdf.worker.min.mjs?url` + `GlobalWorkerOptions.workerSrc`。React 19 的 `react-hooks/set-state-in-effect` 不允许 effect 体内同步 setState——预览组件用 `key={docId}` 重挂载替代状态重置。

**Zilliz 索引自适应**：`sparse_index_type(uri)` —— uri 含 "zilliz"（zillizcloud.com / *.cloud.zilliz.com，dedicated 与 serverless）→ AUTOINDEX；自托管 Milvus → 显式 SPARSE_INVERTED_INDEX（AUTOINDEX 不覆盖 BM25 稀疏字段）。

---

## 2026-09-29

### 知识库 v1 集成（Unstructured + Milvus/Zilliz + BM25/Dense 混合检索）

设计见 ADR-0004，模块落位见 architecture.md §3/§6。实现要点与版本勘察结论：

**pymilvus 3.0.2（注意：已是大版本 3.x，API 以实测为准）**

- 关键签名实测：`MilvusClient.hybrid_search(collection_name, reqs, ranker, limit, output_fields) -> List[List[dict]]`（命中为 dict，含 `entity`/`distance`）；`AnnSearchRequest(data, anns_field, param, limit, expr=...)`；`RRFRanker(k=60)`；`FunctionType.BM25` 存在。
- Schema 构建：`MilvusClient.create_schema(auto_id=True, enable_dynamic_field=False)` 返回 `CollectionSchema`，`add_field(name, dtype, **kwargs)` / `add_function(Function)`；`prepare_index_params` 是 **classmethod**（实例上调用即可）。
- BM25 稀疏向量完全由服务端生成：插入行**不含** sparse 字段，稀疏检索 `data=[query 原文]`；`enable_dynamic_field` 与 BM25 Function 同开有已知插入 bug（milvus#40581），故显式关闭 dynamic field。
- 索引：dense → `AUTOINDEX`(COSINE)；sparse → 必须显式 `SPARSE_INVERTED_INDEX` + `metric_type="BM25"`（AUTOINDEX 不适用 BM25 稀疏字段）。
- 中文分析器：`analyzer_params={"type": "chinese"}`（jieba 系）。**分析器与 dim 在建 collection 时固定**，切换需删库重建重灌。
- `pymilvus` 仅允许 `app/services/kb_vector_store.py` import——`scripts/check-boundaries.mjs` 新增规则强制（AGENTS.md §2 同步更新）。

**httpx 0.28.1（multipart 编码变更）**

- `data=` 不再接受元组列表（`TypeError: sequence item 0: expected a bytes-like object`）。重复字段改用 **dict + 列表值**：`data={"languages": ["chi_sim", "eng"]}`，实测展开为两个同名 multipart part（PITFALLS 同日条目）。

**FastAPI multipart**

- `UploadFile` 路由要求 `python-multipart`，缺失在**路由注册（导入）期**抛 RuntimeError 而非请求期。已声明为直接依赖。

**入库管线与降级策略**

- `BackgroundTasks.add_task(sync_fn, ...)`：sync 回调由 Starlette 放线程池执行，不阻塞事件循环（SSE 聊天可并发进行）。
- 上传落盘名 `{doc_id}__{filename}`（防同名覆盖），sha256 流式计算去重；reingest 先按 `doc_id` 删旧向量再插入，保证幂等。
- 优雅降级：`CREO_KB_ENABLED=true` 但 `CREO_MILVUS_URI` / `CREO_UNSTRUCTURED_API_URL` / `CREO_KB_EMBEDDING_BASE_URL` 任一缺失，或 Milvus 连接失败 → KB 栈不注册（KB 端点 503、工具不注入），Agent 主链路不受影响。
- 进程重启时 in-flight 文档停在 `processing`：用 `/knowledge` 页的重试按钮 reingest 恢复。
- 前端挂载期 fetch 需遵守 eslint react-hooks 7.1 新规则 `set-state-in-effect`：setState 必须放在 promise 回调里（useAgent 用 zustand setter 所以从未触发过该规则）。

---

## 2026-09-25（夜）

### .env 加载机制修正（provider 原生 key）

背景与根因见 PITFALLS 同日条目。实现决策：

- `load_env_file()` 放在 `app/core/config.py` **模块导入时**执行（`get_settings` 有 lru_cache，必须先于首次构造）；路径用 `Path(__file__).resolve().parents[2]` 定位 backend 根，**与启动 cwd 无关**。
- `override=False`：真实 shell 环境变量 > `.env` 文件，符合 12-factor 预期，容器/CI 注入不受文件干扰。
- `python-dotenv` 从传递依赖提升为**直接依赖**（我们直接 import 它，按依赖纪律声明）。
- 测试隔离模式：`Settings(_env_file=None)` + 清除 ambient `CREO_*`（`tests/test_model.py`），此前 `test_settings_defaults` 在装有真实 `.env` 的机器上必然失败 —— 环境相关测试必须密闭。

---

## 2026-09-25（晚）· 补充

### OpenBitFun 调研：可借鉴实践

调研了同类产品 OpenBitFun（Rust workspace + 多端 React 前端 + 独立 design-system 包 + 四种 Agent Harness 模式），完整采纳清单见 `docs/architecture.md` §9。本次落地的两项：

1. **文档规则自动化**（借鉴其 check-scripts 文化：`check-core-boundaries` / `theme:color-audit` / `typography:audit`）。新增 `scripts/check-boundaries.mjs`（Node 零依赖）强制：只有 `app/agent/**` 可 import 深度学习框架模块；routes 不得直连 agent 内部；services 不得依赖 agent；前端 components 不得直连 services/SSE；store 不得有网络；`components/ui` 只许依赖 `@/lib/utils`；TS/TSX 禁止硬编码十六进制颜色（DESIGN.md §2）。已接入 pre-commit 第一道检查。
2. **分层模块索引表**（借鉴其根 AGENTS.md 的 Layered Module Index 写法）写入 AGENTS.md §2。

**评估后暂缓的项**（避免过度工程）：token 管线（design-tokens 包 + 密度变体，Creo 规模下 index.css 变量已够）；事件协议状态机化（applyAgentEvent 纯函数 + 序列测试已等价覆盖 MVP）；models.dev 快照驱动的模型选择器（当前 env 配置已满足多 provider 需求，做 UI 选择器时再引入）；嵌套 AGENTS.md 与 release-please（仓库规模/远端仓库前置条件未到）。

---

## 2026-09-25（晚）

### LLM 配置开放自定义（多 provider / base_url）

原设计 `CREO_MODEL="openai:gpt-4o-mini"` 单字符串 + provider 原生 key 环境变量，无法接 OpenAI 兼容第三方端点。改为四个配置项：

```text
CREO_MODEL_PROVIDER / CREO_MODEL_NAME / CREO_MODEL_API_KEY / CREO_MODEL_BASE_URL
```

实现要点：

- `create_model(provider, name, api_key, base_url)` 调 `init_chat_model(name, model_provider=provider, **kwargs)`。注意参数名是 **`model_provider`**（init_chat_model 的 model 参数本身只放模型名）。
- `api_key` / `base_url` **只在非空时透传**：google_genai 等 provider 的 ChatModel 没有 `base_url` 字段，传了会 pydantic 校验报错；空值则回落 provider 原生行为（原生 env key、官方端点）。
- OpenAI 兼容服务（DeepSeek/Qwen/Moonshot/GLM/Ollama/vLLM）= `provider=openai` + 自定义 `base_url`，langchain-openai 的 ChatOpenAI 原生支持这两个字段。
- 健康/日志展示用 `Settings.model_display`（`provider:name`）拼装，配置项保持原子。

放弃的方案：`CREO_MODEL` 继续作为 "provider:model" 双轨兼容 —— 两种写法并存容易踩配置优先级的坑，MVP 直接切换并在 .env.example 给全示例。

---

## 2026-09-25（下午）

### 前端包管理器切换到 pnpm

**决定**：前端统一使用 pnpm，版本由 `frontend/package.json` 的 `packageManager` 字段锁定（当前 `pnpm@12.4.1`）。后端仍为 uv。规则写入 AGENTS.md §11 与 CONTRIBUTING.md §6。

**原因**：

- 内容寻址存储省磁盘、安装快；
- **严格依赖**：默认不提升传递依赖（无"幽灵依赖"），`pnpm exec esbuild` 不可用是预期行为 —— 只能通过直接依赖的入口使用；
- `packageManager` 字段 + corepack 可复现工具链版本；
- pnpm 12 内置供应链校验（install 时对 lockfile 逐条校验发布时间策略，380 条约 7.5s）。

**pnpm 12.4.1 实测发现（与旧资料差异）**：

- 仓库级配置已迁移到 **`pnpm-workspace.yaml`**，package.json 的 `pnpm.onlyBuiltDependencies` 字段**被忽略**（见 PITFALLS 同日条目）；
- 首次 `pnpm install` 会自动生成 `pnpm-workspace.yaml` 占位（`allowBuilds: esbuild: set this to true or false`），并因供应链策略自动写入 `minimumReleaseAgeExclude: [lucide-react@1.48.0]`（该包发布时间过新）；
- 构建脚本放行格式为 `allowBuilds` 布尔映射，当前放行 `esbuild` 与 `@tailwindcss/oxide`（两者原生二进制经 optional deps 提供，postinstall 仅做校验/链接）。

**变更范围**：`package.json`（+packageManager）、`pnpm-lock.yaml`（替代 package-lock.json）、`pnpm-workspace.yaml`（新增）、`frontend/Dockerfile`（corepack 拉起 pnpm + `--frozen-lockfile`；运行时直接复制自包含的 node_modules 并用 `node_modules/.bin/vite` 启动 preview）、`scripts/pre-commit-check.sh`、README / CONTRIBUTING / AGENTS / architecture 文档命令。

---

## 2026-09-25

### DeepAgents Integration（安装版本 0.7.18 勘察结果）

按 AGENTS.md §12 流程：先 `inspect` 实际安装版本，再用最小探针脚本（ScriptedChatModel + calculator）跑通真实 graph 流，确认以下事实后才写 runtime：

- **deepagents 0.7.18 建立在 LangChain 1.x 中间件架构上**（`langchain.agents.middleware`），不再是早期 0.0.x 的裸 LangGraph 封装。
- `create_deep_agent` 的系统提示词参数是 **`system_prompt`**，旧资料中的 `instructions` 参数不存在；`model` 可传模型字符串或实例；**`checkpointer` 是一等参数**（传 `MemorySaver()`，配合 `config={"configurable": {"thread_id": session_id}}` 实现会话记忆）。
- 流事件形状（`astream(..., stream_mode=["messages","updates"], subgraphs=True)`）：每一项是 **3 元组 `(namespace, mode, payload)`**。
  - `messages` 模式 payload 为 `(chunk, metadata)`：chunk 是 `AIMessageChunk`（token 增量；每个 model 调用结束时附一个空内容、`chunk_position="last"` 的哨兵块）或完整 `ToolMessage`。
  - `updates` 模式 payload 为 `{node: state_delta}`：`model` 节点 delta 含完整 `AIMessage`（`tool_calls` 已解析为 dict），`tools` 节点 delta 含 `ToolMessage`；middleware 产生的节点 delta 可能是 `None`，必须防御。
- `ToolMessage` 会**同时**出现在 messages 与 updates 两种模式里 → runtime 按 `tool_call_id` 去重（先到先得）。
- `AIMessageChunk.tool_calls` 在流式过程中只含已完整解析的调用，**不可靠** → `tool_start` 只从 updates 模式的完整 `tool_calls` 发出（保证 args 是完整 JSON 对象，符合 ADR-0002 约定）。
- 分段消息（message_start/end 多段）通过 `chunk.id`（同一 model 调用内稳定）+ `chunk_position="last"` 哨兵 + tool_start 前强制关闭三条信号共同确定。
- deepagents 0.7.18 **不自带 langchain-openai**（只带 anthropic / google-genai 集成）→ 显式添加 `langchain-openai` 依赖，默认模型用 `openai:gpt-4o-mini`。

放弃的方案：透传 LangGraph 原始事件给前端（违背 ADR-0002）；在 runtime 里同时消费 messages 的 tool_call_chunks 增量（部分 JSON 无法保证 args 完整性，不值得为渐进式 args 显示增加协议事件）。

### Agent Runtime 事件转换器（关键实现细节）

- `messages` 模式只负责文本增量与消息生命周期；`updates` 模式只负责 tool_start / tool_result。两种模式天然有序（模型 token 先于节点完成事件，节点完成先于 tools 节点执行）。
- 客户端断连时 `GeneratorExit`（BaseException）不被 `except Exception` 捕获 → 不会在已关闭的 async generator 里继续 yield（避免 `RuntimeError: async generator ignored GeneratorExit`）。
- `AgentRuntime` 采用 lazy builder：模型初始化失败（如缺 API key）不在启动时崩溃，而是首个请求流式返回 `error` 事件，health 端点展示 `agent: pending`。

### Tool 错误隔离

langchain 1.x 的 ToolNode 对意外异常默认**向上抛出**（`_default_handle_tool_errors`），会终止整个 run。用 `create_deep_agent(middleware=[ToolErrorMiddleware()])` 拦截：捕获工具异常并返回 `status="error"` 的 ToolMessage → 协议的 `tool_result.isError=true`，UI 显示错误态、模型可自行恢复。未来新增工具自动获得此行为。

### SSE 实现细节

- 后端手写帧编码（`event:` + `data:` + 空行），不引入 sse-starlette（依赖纪律）；响应头 `Cache-Control: no-cache`、`X-Accel-Buffering: no`。
- 前端 `fetch` + `ReadableStream` + 纯函数帧解析器（`lib/sse.ts`，可单测）；`EventSource` 因不支持 POST 被排除（ADR-0003）。
- Vite dev proxy 与 `vite preview` 均配置 `proxyTimeout: 0` 防止流被缓冲。

### 前端状态设计

- `agentStore.applyAgentEvent(state, sessionId, event)` 是纯函数（单测覆盖全事件序列）；zustand 只是对它的薄封装。
- 一次 Run 的助手输出聚合为一条消息，内部按序混排 text / tool 两类 part —— 对应设计稿「Agent 过程 + 最终答案」的视觉结构。
- 事件驱动、无轮询；流结束后拉取一次会话列表以对齐服务端标题/时间戳。

### 已知技术债（Debt）

- 前端 bundle 654KB（gzip 203KB），超过 Vite 500KB 警告线：react-markdown + highlight.js 占大头。后续可做 manualChunks / 动态 import。
- 会话记忆与历史存在进程内（MemorySaver），重启即失 —— MVP 预期行为，接口已隔离（SessionService / checkpointer 可替换）。
- 历史恢复时 `AIMessage.id` 直接复用框架 id；跨进程重启后 id 稳定性依赖框架实现。
- docker-compose / Dockerfile 提供为本地编排脚手架，**本环境无 Docker 未实测**（已知限制，首次使用时验证）。
