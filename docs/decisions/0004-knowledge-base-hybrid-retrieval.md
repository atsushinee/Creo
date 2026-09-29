# ADR-0004: 知识库 v1（PDF 上传 + BM25/Dense 混合检索）

## Status

Accepted（2026-09-29）

## Context

MVP（Agent 基础链路）稳定后，需要把本地 PDF 沉淀为可检索的知识：上传 → 分类 → 解析 → 向量化入库 → Agent 检索引用。既有环境：自托管 Unstructured API（Partition Endpoint）、Zilliz Cloud（Enterprise 专用集群）；语料以纯中文为主；embedding 选定 **bge-m3（1024 维）**；解析策略选定 **hi_res**（扫描件兜底 OCR）。

这一步使 AGENTS.md §1 中预留的 RAG / Knowledge Base 边界**正式进入实现范围**（范围变更，AGENTS.md 与 architecture.md 已同步更新）。

## Decision

1. **分类建模为多知识库（KB）**：一个 KB = 本地目录（上传原件 + SQLite 登记，stdlib `sqlite3`）+ 一个 Milvus collection（`kb_{slug}_{id8}`）。删除语义 = drop collection + 删目录。
2. **解析走自托管 Unstructured Partition Endpoint**（`POST /general/v0/general`，multipart）：`strategy=hi_res`、`chunking_strategy=by_title`、`max_characters=1500`、`new_after_n_chars=1200`、`combine_text_under_n_chars=300`、`include_orig_elements=false`、`pdf_infer_table_structure=true`、`languages=chi_sim,eng`。只用 httpx 调 HTTP，不引入 `unstructured` Python 包（依赖纪律）。
3. **稀疏检索用 Milvus 服务端 BM25 Function**：`text`（VARCHAR，`enable_analyzer=True`，`analyzer_params={"type":"chinese"}`）经 `Function(FunctionType.BM25)` 自动生成 `sparse`（SPARSE_FLOAT_VECTOR）；**插入只写原文，查询直接传 query 文本**，BM25 打分由 Milvus（Tantivy）在服务端完成。不引入客户端 bm25 嵌入。
4. **密集检索用 OpenAI 兼容 `/embeddings`**（默认 `BAAI/bge-m3`，1024 维），httpx 直连，分批 + 重试。
5. **检索 = `MilvusClient.hybrid_search`**（dense AnnSearchRequest + sparse AnnSearchRequest，`RRFRanker(60)`，sparse 侧 `drop_ratio_search=0.2`）；跨 KB 检索在应用层做 RRF 融合。
6. **索引**：dense → `AUTOINDEX`（COSINE）；sparse → `SPARSE_INVERTED_INDEX`（BM25，AUTOINDEX 不适用 BM25 稀疏字段）。
7. **入库为进程内后台任务**（FastAPI `BackgroundTasks`：sync 回调由 Starlette 放线程池执行），文档状态机 `pending → processing → ready/failed` 存 SQLite，前端轮询。不引入任务队列。
8. **Agent 集成**：`search_knowledge_base` 工具（`tools/knowledge_tools.py` 工厂闭包注入 `KbSearchService`）；**事件协议零变更**（复用 `tool_start`/`tool_result`；`source_added` 仍预留）。
9. **配置开关 `CREO_KB_ENABLED`（默认 false）**；未配置 Milvus / Unstructured / Embedding 时 KB 端点与工具整体不注册，Agent 主链路不受影响（优雅降级）。

## Update（2026-09-29 晚）：解析后端切换为 Unstructured Transform API

实际环境核查后，解析服务不是自托管 Partition Endpoint，而是 **Unstructured Transform API**（transform.unstructured.io，官方 SDK `unstructured-transform-client` 0.18.21）。受影响的决策点：

- **Decision 2 作废**：v2 无 chunking/strategy/OCR-language 参数。分块移到客户端 `pack_elements()`（连续叙事元素贪心打包至软限制 ≈80% max_chars、Table 独立成块、超长元素硬切、<20 字符丢弃）；`CREO_UNSTRUCTURED_PROFILE=best` 取代 hi_res 质量档（balanced/best/fast）。
- 页码引用保留：`Element.metadata.page_number`（1-based）默认返回；表格 HTML 经 `include=["text_as_html"]` 获取（取代 `pdf_infer_table_structure`）。
- 新增直接依赖 `unstructured-transform-client`；连接配置改为 `CREO_UNSTRUCTURED_API_KEY`（必需）+ 可选 `CREO_UNSTRUCTURED_SERVER_URL`（旧名 `CREO_UNSTRUCTURED_API_URL` 经 AliasChoices 兼容，`/api/v2` 后缀自动剥离——SDK 自己拼接 API 路径）。
- **Decision 6 修订（索引选择自适应）**：Zilliz Cloud（dedicated 与 serverless）只接受 AUTOINDEX；自托管 Milvus 的 BM25 稀疏字段必须显式 `SPARSE_INVERTED_INDEX`。`sparse_index_type(uri)` 按 uri 自动选择。

其余决策（每 KB 一 collection、服务端 BM25 Function、RRF 混合检索、BackgroundTasks、事件协议零变更、优雅降级）不变。

## Alternatives

| 方案 | 不选原因 |
| --- | --- |
| 单 collection + partition key 多租户 | KB 数量上来之前复杂度收益为负；单文档/整库删除语义更绕；接口已按 collection 隔离，未来可迁 |
| 客户端 BM25（pymilvus model / bm25s）预计算稀疏 | 需自行维护语料统计与分词一致性；服务端 Function 原生完成，省一整层状态 |
| BGE-M3 lexical weights 替代 BM25 | 需要模型同时产出 dense+sparse，与「先跑通 BM25 + dense」的 v1 目标不符，留作演进 |
| 任务队列（Celery / RQ / arq） | MVP 单进程规模不需要；BackgroundTasks + 状态机可观测、零新依赖 |
| 入库进度走 SSE 事件流 | 需先改 ADR-0002 事件协议；轮询文档状态已满足 v1 |
| langchain UnstructuredLoader / unstructured 包 | 会拖入整包解析依赖栈；自托管场景一个 httpx 调用即可 |
| npm/自研前端上传队列、WebSocket 进度 | 同上，轮询即可 |

## Consequences

- `pymilvus` 成为直接依赖（**仅** `services/kb_vector_store.py` 可 import，边界脚本强制）；`httpx` 从 dev 提升为运行时依赖。
- bge-m3 换模型 / 换维度 = 重建全部 collection 并重灌（dim 在配置中，重建流程：删除 KB 后重建并 reingest）。
- 中文分析器（`chinese`/jieba）在**建 collection 时固定**；切换分析器同样需要重建 collection。
- 进程重启会丢失 in-flight 入库：文档停留在 `processing`，可用 reingest 恢复（v1 接受，TECHNICAL-NOTES 有说明）。
- 事件协议、Runtime、ToolCallCard 均未改动；未来如需「来源卡片」，走预留的 `source_added`（先改 ADR-0002）。
