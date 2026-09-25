# CONTRIBUTING.md

本文件描述 Creo 的开发流程与提交规范。架构规则见 [AGENTS.md](AGENTS.md)，UI 规范见 [DESIGN.md](DESIGN.md)。

---

## 1. 开发流程

每次修改代码都遵循：

```text
Understand → Plan → Implement → Test → Document → Review
```

开始前必读（顺序固定）：

1. `AGENTS.md`
2. `DESIGN.md`
3. `docs/architecture.md`
4. 相关 ADR
5. 最近的 `docs/development/CHANGELOG.md`
6. 相关 `docs/development/TECHNICAL-NOTES.md`
7. 相关 `docs/development/PITFALLS.md`

---

## 2. 本地开发

### 后端

```bash
cd backend
cp .env.example .env        # 填入 LLM API key
uv sync                     # 安装依赖（uv）
uv run pytest               # 测试
uv run ruff check .         # lint
uv run uvicorn app.main:app --reload --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run typecheck           # tsc --noEmit（strict 模式）
npm run lint                # eslint
npm run test                # vitest
npm run build               # 产出 dist/
npm run dev                 # http://localhost:5173
```

---

## 3. Pre-commit 检查

**任何 commit 之前必须执行：**

```bash
bash scripts/pre-commit-check.sh
```

脚本会依次执行：后端（ruff + pytest + import check）、前端（typecheck + lint + test + build）。任一步失败则不得提交。

### Pre-commit Checklist

```text
[ ] Code compiles
[ ] Tests pass
[ ] Type check passes
[ ] Lint passes
[ ] No secrets committed（检查 .env / API key / password / token）
[ ] CHANGELOG updated
[ ] TECHNICAL-NOTES updated
[ ] PITFALLS updated（没有踩坑也必须写 "No significant pitfalls encountered."）
[ ] ADR updated if necessary
[ ] git diff reviewed
[ ] Commit message follows Conventional Commits
```

启用可选的 git hook（每次 `git commit` 自动执行检查脚本）：

```bash
git config core.hooksPath .githooks
```

---

## 4. Commit Message

Conventional Commits：

```text
feat:     新功能            feat(agent): add SSE streaming events
fix:      修复              fix(ui): prevent duplicate tool result rendering
refactor: 重构（不改行为）   refactor(store): extract event reducer
perf:     性能
docs:     文档              docs: record DeepAgents integration details
test:     测试
chore:    杂务 / 工具
build:    构建系统 / 依赖
ci:       CI
```

scope 建议：`agent` / `ui` / `api` / `session` / `tools` / `docs` / `deps`。

---

## 5. 文档义务（强制）

每次提交必须让文档能回答：

| 问题 | 记录位置 |
| --- | --- |
| What changed? | `docs/development/CHANGELOG.md` |
| Why? / How? | `docs/development/TECHNICAL-NOTES.md` |
| Problems? / Solution? | `docs/development/PITFALLS.md` |
| 架构级决策 | `docs/decisions/`（新 ADR） |
| 是否产生技术债 | `TECHNICAL-NOTES.md` 的 Debt 小节 |

没有踩坑时，`PITFALLS.md` 中对应条目写：

```markdown
No significant pitfalls encountered.
```

不要为了凑内容虚构问题。

---

## 6. 依赖纪律

添加任何依赖前回答：

```text
Why do we need it? / What problem does it solve?
Can existing dependencies solve it? / What is the maintenance cost?
```

新增重要依赖必须在 `TECHNICAL-NOTES.md` 记录原因。当前阶段禁止引入 RAG / 向量库 / MCP / 认证等大型依赖。

---

## 7. API 兼容性

所有第三方 API（DeepAgents / LangChain / FastAPI / React / Vite / Tailwind）以**当前安装版本**为准。文档与实际不符时：

```text
Inspect installed package → Inspect type definitions → Inspect official docs
→ Run minimal reproduction → Record result（写入 TECHNICAL-NOTES.md）
```

禁止编造 API，禁止根据旧博客写代码。

---

## 8. Definition of Done

```text
Code + Test + Documentation + Review
```

缺一不可。
