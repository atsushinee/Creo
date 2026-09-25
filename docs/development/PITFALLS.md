# Pitfalls

记录踩坑：Problem / Cause / Solution / Lesson。任何值得以后避免的问题都必须记录。没有踩坑时明确写 `No significant pitfalls encountered.`，不要虚构问题。

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
