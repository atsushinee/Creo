# Milestone: Knowledge Base v1（ADR-0004）

> 目标：PDF 上传 → 解析切块 → BM25/Dense 混合入库 → Agent 检索引用的完整知识库链路，含可观测（追踪/召回测试）与容错。
>
> 状态：**已交付**（2026-09-30）。自动验证覆盖组件级与链路级（fake/注入双打 + 真实服务冒烟）；带 🔑 的条目需要在真实 UI 中手工确认一遍。

## Case 1 — 上传与解析入库

- [x] 创建多个知识库（分类），PDF multipart 上传，sha256 去重（重复 409）、大小上限（413）（test_kb_api）。
- [x] 后台管线：Unstructured Transform API 解析（hi_res 质量档 profile=best）→ 客户端分块（连续元素贪心打包 + 表格独立 + 超长硬切）→ bge-m3 向量化 → Milvus 写入（服务端 BM25 Function 自动生成稀疏向量）（test_ingestion）。
- [x] 状态机 pending → processing → ready/failed，前端轮询（test_kb_api）。
- [x] 失败可一键 reingest，幂等（先删旧向量；解析/向量化阶段走内容寻址缓存，不重复计费）（test_ingestion）。
- [x] 🔑 真实服务冒烟：yushu.pdf（54 页章程）全链路 ready，33 chunks（scripts/smoke_kb.py，数据见 TECHNICAL-NOTES）。

## Case 2 — 混合检索与 Agent 引用

- [x] `search_knowledge_base`：MilvusClient.hybrid_search（dense COSINE + sparse BM25）+ RRFRanker，跨库 RRF 融合（test_kb_search_and_store）。
- [x] 服务端 BM25 Function：插入不写 sparse、查询传原文；中文分析器（chinese/jieba）建库时固定。
- [x] 引用格式 `[1] 文件名 (page N)`，页码来自 Unstructured 元数据。
- [x] 🔑 真实 UI 手工确认：Chat 页跨库提问 + Knowledge 页文档定向提问的引用准确性。

## Case 3 — 文档定向对话（doc-chat）

- [x] 每 (kb, doc) 独立 Agent 实例（独立系统提示词 + `search_document` 闭包绑定文档，检索服务端 `doc_id ==` 硬过滤）（test_api: doc scope 到达 runtime）。
- [x] 会话记忆按文档隔离且持久化（共享 AsyncSqliteSaver，线程按 session 隔离）（test_persistence）。

## Case 4 — 可观测

- [x] pipeline_event 表记录 upload/parse/chunk/embed/index 五阶段（状态、detail、耗时），失败记录失败阶段（test_ingestion）。
- [x] `GET .../documents/{id}/trace` + 前端追踪时间线（test_kb_api）。
- [x] 召回测试页：同一查询 hybrid / 仅 dense / 仅 sparse 三路对比（`POST /kb/{id}/search-test`，test_kb_api）。
- [x] 🔑 手工评估三路排序差异，决定是否/何时引入 Rerank。

## Case 5 — 容错与持久化

- [x] 重启恢复：pending/processing 文档标记 failed + 重试提示，已完成阶段缓存不重复计费（test_persistence）。
- [x] 会话与对话记忆持久化（SQLite），重启不丢（test_persistence）。
- [x] Milvus 懒连接：启动零网络调用，远端故障只作用于当次操作（test_persistence）。
- [x] 工具异常 → error ToolMessage（既有 test_runtime / ToolErrorMiddleware）；前端工具卡片 error 态。
- [x] 🔑 手工确认：断网/关掉 Zilliz 后上传与检索的报错文案与恢复流程。

## Case 6 — 界面

- [x] 三栏工作台：文档卡片（第一页封面，懒渲染）+ 定向对话 + 连续滚动预览（页码跳转/首尾快捷键）。
- [x] 自定义弹窗（token 化）：KB 新建/删除、文档删除。
- [x] 长对话渲染优化：MessageItem / MarkdownRenderer / ToolCallCard / Composer memo 化，流式期间仅重渲染在流的消息。
