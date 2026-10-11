# Pitfalls

记录踩坑：Problem / Cause / Solution / Lesson。任何值得以后避免的问题都必须记录。没有踩坑时明确写 `No significant pitfalls encountered.`，不要虚构问题。

---

## [2026-10-12] 引用跳转功能（citation → page jump）

**Problem**：点击答案中的 `[N]` 引用，页面导航到当前路由（`/knowledge`）而不是滚动预览。
**Cause**：react-markdown v9+ 的 `defaultUrlTransform` 只放行安全协议（http/https/mailto 等），自造的 `cite://N` 链接 href 被消毒成空字符串，自定义锚点匹配 `cite://` 失败、回退成普通 `<a href="">`，点击即导航到当前页。
**Solution**：给 `ReactMarkdown` 传自定义 `urlTransform`——`cite://` 前缀原样放行，其余走 `defaultUrlTransform`。
**Lesson**：react-markdown 里用非标准协议做内部链接语义时，必须同时覆盖 `urlTransform`；URL 消毒发生在组件映射之前，只写自定义 `a` 组件拦不住。

---

## [2026-10-12] 元素框选 overlay 无效果（coordinates 形状假设错误）

**Problem**：文档解析缓存里明明有坐标，前端"元素框选"开关打开后一个框都不显示。
**Cause**：开发时实测的坐标形状是 `coordinates.system = { layout_width, layout_height, … }`（对象嵌套），据此写了 `system.layout_width`；但另一批 Unstructured 响应返回的是 `system: "PixelSpace"`（字符串）+ `layout_width/height` **平铺在 coordinates 顶层**。取值得到 0，`boxRect` 直接返回 null。
**Solution**：`boxRect` 兼容两种形状——`system` 为对象时从中取，为字符串时回退到 coordinates 顶层；`ElementCoordinates` 类型同步放宽。
**Lesson**：对外部 API 的响应形状，"上次实测是这样"不等于"永远是这样"——同一供应商不同请求/版本会变。防御性解析要在**首次接线的字段层级**就做双形状兼容，并且用真实入库文档做冒烟验证，而不是只信开发时那一次观察。

---

## [2026-10-12] README 文档补强（Development / Roadmap）

No significant pitfalls encountered.

---

## [2026-09-30] 边界违规入库：只跑子集检查 + 管道 grep 吞掉脚本退出码

### Problem

`components/ui/dialog.tsx`（导入同层 `button.tsx`）违反"ui 层只依赖 @/lib/utils"的边界规则并被提交入库；复盘时发现当时提交前只运行了前端 tsc/eslint/vitest/build 子集，没有跑完整 pre-commit 脚本。后续验证时又用 `bash pre-commit-check.sh | grep …` 查看输出——管道返回 grep 的退出码，脚本失败被吞，带病提交差点再次发生。

### Cause

检查子集化：新增 ui 组件时没意识到 ui 层 import 规则会命中；bash 管道默认返回最后一个命令的退出码，`| grep` 让失败静默通过。

### Solution

1. 规则修订：ui 层允许导入 `@/components/ui/*` 同层原语（shadcn 式组合是合法意图，规则本意是禁止业务模块），正则放宽为 `@\/(?!lib\/utils|components\/ui)`；2. 流程修正：提交前完整运行 pre-commit 脚本且不接管道（或 `set -o pipefail`），以脚本自身退出码为准。

### Lesson

检查脚本的退出码就是契约——任何 `| grep`/`| head` 的"美化输出"都必须以 `pipefail` 或先落日志为前提；新增文件落在受规则约束的目录时，逐条核对目录级规则而不是依赖记忆。

### Related

scripts/check-boundaries.mjs · frontend/src/components/ui/dialog.tsx

---

## [2026-10-03] Transform API 传输层 SSL 失败：SDK 不重试，需适配层定向重试

### Problem

冒烟重跑时 `parse.run` 偶发抛 `ApiException(status=0, reason="SSLError: UNEXPECTED_EOF_WHILE_READING")`，解析失败。若发生在用户 reingest 时，重新入库会再次全额计费一次解析。

### Cause

`unstructured-transform-client` 的内置重试策略：写操作只在"确定未到达服务端"时重试（连接拒绝/DNS）；SSL 握手中断属于"不确定"→ 不重试。但 status=0 恰恰证明没有 HTTP 响应、服务端未处理——不会产生计费。

### Solution

适配层对 `ApiException.status == 0` 的传输失败做最多 2 次补充重试（2s/4s 退避）；HTTP 4xx/5xx 一律不重试（服务端已处理，避免重复计费/重复处理）。

### Lesson

"可安全重试"的判据不是异常类型而是**计费语义**：证明未到达 = 可重试；已到达 = 不重试。SDK 的保守策略合理，调用方要按自己的计费模型补一层。

### Related

backend/app/services/unstructured_client.py · backend/tests/test_kb_clients.py

---

## [2026-09-30] 重启后"KB 消失"：两个叠加根因 + 测试数据泄漏进真实 SQLite

### Problem

用户上传 PDF 后重启后端，页面上 KB/文档列表全空、上传按钮禁用。另外引入会话持久化后，test_api 一跑发现真实 `data/sessions.sqlite` 里冒出 5 条测试会话。

### Cause

三个问题叠加：① 前端 `currentKbId` 挂载时不自动选中，KB 列表在但页面处于"未选择"状态（上传按钮 `!currentKb` 禁用）；② 后端把登记服务与远端可用性耦合，MilvusClient 构造即拨号，启动时 Zilliz 不可达会禁用整个 KB 栈（登记接口 503）；③ hermetic 测试 fixture 只覆盖了环境变量与 KB 开关，没重定向 `data_dir`——持久化一落地测试就写进了真实数据库。

### Solution

① 挂载加载后自动选中第一个 KB 并拉取文档；② Milvus 连接改为懒式（构造零网络，失败只作用于当次操作），登记服务无条件创建；③ conftest 把 `data_dir`/`kb_data_dir` 重定向到 per-test tmp 目录；测试泄漏的真实库数据已清理。

### Lesson

"数据在不在"和"用户看不看得见"是两回事——持久化 bug 的第一动作是直接查落盘文件而不是改代码。测试密闭性必须随持久化面扩大而同步扩大：凡新增落盘点，conftest 就要覆盖。

### Related

backend/app/main.py · backend/app/services/kb_vector_store.py · backend/app/services/session_service.py · backend/tests/conftest.py · frontend/src/hooks/useKnowledgeBase.ts

---

## [2026-09-29] Transform SDK 的 server_url 不能带 /api/v2 路径

### Problem

按控制台示例把 API base（`https://transform.unstructured.io/api/v2`）直接配为 SDK 的 `server_url`，所有请求会拼成 `/api/v2/api/v2/...` 双路径。

### Cause

SDK 生成的 API 路径已包含 `/api/v2` 前缀，`server_url` 只应是主机 origin。

### Solution

适配层 `_normalize_server_url` 自动剥离结尾的 `/api/v2` 与 `/`；配置项用 `AliasChoices` 兼容旧变量名 `CREO_UNSTRUCTURED_API_URL`，存量 `.env` 无需改名。

### Lesson

SDK 的 `server_url`/`base_url` 语义（origin vs 完整 API base）每个库不同，接入前看生成的路径定义而不是示例截图。

### Related

backend/app/services/unstructured_client.py · backend/app/core/config.py · docs/development/TECHNICAL-NOTES.md

---

## [2026-09-29] Zilliz serverless 的 DDL 偶发 DEADLINE_EXCEEDED，cleanup 报错掩盖成功结果

### Problem

冒烟测试全链路（解析→分块→向量化→插入→检索→删除）全部成功，但最后 `drop_collection` 抛 `DEADLINE_EXCEEDED: The upstream server is timing out`，脚本以失败退出——成功结果被清理步骤的噪音掩盖；下一轮重跑又会完整重付 API 费用。

### Cause

serverless 集群的 DDL 路径上游繁忙时会超时（且服务端往往已执行，只是响应没回来）；脚本把"清理失败"当成"测试失败"，且没有任何中间产物缓存。

### Solution

1. `MilvusVectorStore` 全部操作显式 `timeout=60s`；2. 冒烟脚本清理改为 3 次重试 + 启动时自愈清残留 `kb_smoke_*`，清理失败只告警不改变退出码；3. 解析/embedding 按内容指纹缓存到 `data/smoke/`，重跑免费。

### Lesson

"验证成功"与"资源清理"是两个独立结论，finally 里的清理异常必须与主流程解耦；对按调用计费的外部服务，长链路脚本要内置内容寻址缓存，失败重试才不心疼。

### Related

backend/app/services/kb_vector_store.py · backend/scripts/smoke_kb.py · docs/development/TECHNICAL-NOTES.md

---

## [2026-09-29] httpx 0.28 的 multipart 不再接受 data= 元组列表

### Problem

Unstructured 客户端按 requests 时代的写法传 `data=[("strategy", ...), ("languages", "chi_sim"), ...]`，请求直接抛 `TypeError: sequence item 0: expected a bytes-like object, tuple found`。

### Cause

httpx 0.28 的 `data=` 只接受 dict；元组列表不再按 requests 语义展开为表单字段。

### Solution

重复字段用 dict + 列表值表达：`data={"languages": ["chi_sim", "eng"]}`，实测 httpx 会展开为两个同名 multipart part。

### Lesson

httpx 请求体编码参数的语义随大版本变化；multipart 行为以当前安装版本实测为准（AGENTS.md §12 的流程这次又救了一命——先 inspect 再写代码）。

### Related

backend/app/services/unstructured_client.py · backend/tests/test_kb_clients.py · docs/development/TECHNICAL-NOTES.md

---

## [2026-09-29] 同名 PDF 二次上传被拒时会删掉第一次的落盘文件

### Problem

同一 KB 内同名文件重复上传，sha256 去重按预期拒绝了请求，但第一次上传的原件文件被删除（登记行还在，路径悬空）。测试 `test_save_upload_writes_file_and_dedupes` 抓住。

### Cause

落盘路径只用了 `{kb_id}/files/{filename}`，同名文件共享同一路径；重复上传清理自己半成品时 `unlink` 的正是第一次上传的文件。

### Solution

落盘名改为 `{kb_id}/files/{doc_id}__{filename}`，每份上传路径唯一；测试补断言"重复上传被拒后原件仍存在"。

### Lesson

"内容去重"与"路径唯一"是正交的两件事：即使按 hash 拒绝重复，写盘路径也必须先做到互不覆盖。

### Related

backend/app/services/kb_service.py · backend/tests/test_kb_service.py

---

## [2026-09-29] UploadFile 路由缺 python-multipart 在导入期崩溃

### Problem

pytest 收集阶段整个 app 导入失败：`RuntimeError: Form data requires "python-multipart" to be installed`，连带所有既有 API 测试一起挂。

### Cause

FastAPI 的 multipart 支持是可选依赖；含 `UploadFile` 参数的路由在**注册（导入）时**就校验依赖，而不是等到第一个请求。

### Solution

`uv add python-multipart` 并声明为直接依赖。

### Lesson

FastAPI 的可选 I/O 依赖（multipart / orjson 等）按需显式声明；"能 import"不等于"路由能注册成功"。

### Related

backend/pyproject.toml · backend/app/api/routes/knowledge.py

---

## [2026-09-25] 写在 .env 里的 provider 原生 key（OPENAI_API_KEY）不生效

### Problem

用户按 `.env.example` 在 `backend/.env` 里填了 `OPENAI_API_KEY=sk-...`，发起对话仍报 `OpenAIError: Missing credentials`。`CREO_` 前缀的配置（如 `CREO_MODEL_API_KEY`）却一直正常。

### Cause

两套读取机制互不相通：pydantic-settings 只把 **`CREO_` 前缀**的变量从 `.env` 映射进 Settings 字段；而 openai/anthropic SDK 是从**进程环境变量** `os.environ` 读原生 key 的 —— 没有任何代码把 `.env` 里的 `OPENAI_API_KEY` 装进 `os.environ`。另外 `env_file=".env"` 是相对 cwd 解析的，从别的目录启动服务时连 `CREO_*` 也会失效。

### Solution

`app/core/config.py` 新增 `load_env_file()`（python-dotenv 显式声明为直接依赖），在模块导入时、Settings 首次构造前，以**相对 backend 包定位的绝对路径**加载 `.env` 进 `os.environ`（`override=False`，真实 shell 环境变量优先）。新增 `tests/test_config.py` 守护该行为。

### Lesson

`.env` 文件里有两类变量时（框架自有前缀 + provider 原生 key），必须明确每一类由谁加载；pydantic-settings 的 `env_file` 不等于 `export`。涉及环境变量的测试要密闭（`Settings(_env_file=None)` + 清理 ambient env），否则会被开发者本机的 `.env` 污染。

### Related

backend/app/core/config.py · backend/tests/test_config.py · docs/development/TECHNICAL-NOTES.md

---

## [2026-09-25] pnpm 12 忽略 package.json 里的 onlyBuiltDependencies

### Problem

按 pnpm 10 的旧写法把 `pnpm.onlyBuiltDependencies` 写进 `package.json`，`pnpm install` 仍报 `ERR_PNPM_IGNORED_BUILDS`（esbuild 构建脚本被忽略）。

### Cause

pnpm 11+/12 把仓库级配置迁到了 `pnpm-workspace.yaml`；package.json 的 `pnpm` 字段不再被读取。

### Solution

在 `frontend/pnpm-workspace.yaml` 用 `allowBuilds` 布尔映射放行 `esbuild` 与 `@tailwindcss/oxide`。

### Lesson

pnpm 大版本间配置位置会迁移；以当前版本的 install 报错提示与自动生成的配置文件为准，不按记忆或旧文写配置。

### Related

frontend/pnpm-workspace.yaml · docs/development/TECHNICAL-NOTES.md

---

## [2026-09-25] deepagents 0.7.18 API 与旧资料不一致

### Problem

网上示例代码使用 `create_deep_agent(instructions=...)`、无 checkpointer 支持；实际安装版本（0.7.18）没有 `instructions` 参数。

### Cause

deepagents 从 0.0.x 的裸 LangGraph 封装迁移到了 LangChain 1.x 中间件架构，API 已变；示例来自旧版本。

### Solution

以安装版本为准：`inspect.signature` 确认参数为 `system_prompt`，且 `checkpointer` 为一等参数。用最小探针脚本验证后再写 runtime，结论记录于 TECHNICAL-NOTES.md。

### Lesson

任何 LangChain 系依赖升级都必须重跑「inspect 安装包 + 最小复现」流程，不能按旧博客写代码。

### Related

backend/app/agent/agent.py · docs/development/TECHNICAL-NOTES.md

---

## [2026-09-25] 工具异常会终止整个 Agent Run

### Problem

calculator 抛出 `ZeroDivisionError` 后整个 astream 流直接报错，前端只能显示一条 error 事件，MVP Case 3（工具失败但对话继续）无法达成。

### Cause

langchain 1.x 的 ToolNode 默认 `_default_handle_tool_errors` 会把意外异常向上抛出，而不是像 langgraph-prebuilt 旧版那样默认转成错误 ToolMessage。

### Solution

新增 `ToolErrorMiddleware`（`awrap_tool_call` / `wrap_tool_call`），捕获异常并返回 `status="error"` 的 ToolMessage。模型收到错误信息后可自行恢复，协议层 `tool_result.isError` 语义成立。

### Lesson

「框架默认行为」在不同大版本间会翻转；错误路径必须有集成测试（test_runtime.py::test_tool_error_is_reported_not_raised）。

### Related

backend/app/agent/tool_errors.py · backend/app/agent/agent.py

---

## [2026-09-25] `app = create_app()` 遮蔽同名包导致二次调用崩溃

### Problem

`backend/app/main.py` 里 `import app`（包）之后又执行 `app = create_app()`（模块级变量），第二次调用 `create_app()` 时 `app.__version__` 解析到 FastAPI 实例，抛出 `AttributeError`。

### Cause

Python 模块级名字遮蔽：首次 `app = create_app()` 之后，模块全局 `app` 不再指向包。

### Solution

改为 `from app import __version__`，不再依赖 `app` 这个名字指向包。

### Lesson

包名（`app`）与包内模块级变量名不要同名；版本号等常量用 `from ... import` 显式绑定。

### Related

backend/app/main.py · backend/app/api/routes/health.py

---

## [2026-09-25] TypeScript 在 `await Promise<never>` 后丢失窄化

### Problem

`if (!response.ok || !body) { await parseError(response); }`（parseError 返回 `Promise<never>`）之后，TS 仍报 `body` possibly null。

### Cause

never-returning 函数的窄化只对显式返回 `never` 的同步调用生效；`async` 函数返回 `Promise<never>`，await 之后 TS 无法证明控制流不继续。

### Solution

把「读错误详情」与「抛出」拆开：`if (...) { throw new ApiError(await readErrorDetail(response), response.status); }` —— throw 语句本身给出控制流收束。

### Lesson

需要利用 never 窄化时，让分支内直接 `throw`，不要依赖 async helper 的返回类型。

### Related

frontend/src/services/agentApi.ts
