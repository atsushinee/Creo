# Changelog

记录**用户可感知**的功能变化。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本遵循 SemVer。

## [Unreleased]

### Changed

- 前端包管理器从 npm 切换为 **pnpm**：`package.json` 以 `packageManager` 锁定 pnpm@12.4.1，lockfile 由 package-lock.json 换为 pnpm-lock.yaml，新增 pnpm-workspace.yaml（构建脚本放行与供应链策略配置），Dockerfile 与 pre-commit 脚本同步更新。

### Added

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
