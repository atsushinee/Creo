# Technical Notes

记录技术实现细节：为什么这样设计、放弃了什么方案、API 版本差异、关键实现细节、性能与兼容性问题。新条目加在最上面。

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
