"""IngestionService orchestration with fake clients (ADR-0004)."""

import io
import json
from pathlib import Path
from typing import Any

from app.services.ingestion_service import IngestionService, pack_elements
from app.services.kb_service import KbDocument, KnowledgeBase, SqliteKnowledgeService
from app.services.pipeline_cache import PipelineCache


class FakeUnstructured:
    def __init__(self, elements: list[dict] | None = None, error: Exception | None = None):
        self.elements = elements or []
        self.error = error
        self.calls: list[tuple[Path, str]] = []

    def parse_pdf(self, path: Path, filename: str) -> list[dict]:
        self.calls.append((path, filename))
        if self.error is not None:
            raise self.error
        return self.elements


class FakeEmbeddings:
    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.batches.append(list(texts))
        return [[0.1, 0.2] for _ in texts]


class FakeVectorStore:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.collections: list[str] = []
        self.deleted: list[tuple[str, str]] = []

    def ensure_collection(self, name: str) -> None:
        self.collections.append(name)

    def insert_chunks(self, name: str, rows: list[dict[str, Any]]) -> int:
        self.rows.extend(rows)
        return len(rows)

    def delete_doc(self, name: str, doc_id: str) -> None:
        self.deleted.append((name, doc_id))


def make_pipeline(
    tmp_path: Path,
    elements: list[dict] | None = None,
    error: Exception | None = None,
    chunk_strategy: str = "pack",
) -> tuple[SqliteKnowledgeService, KnowledgeBase, KbDocument, IngestionService, FakeVectorStore]:
    kb_service = SqliteKnowledgeService(tmp_path / "kb")
    kb = kb_service.create_kb("docs")
    doc = kb_service.save_upload(kb.id, "manual.pdf", io.BytesIO(b"%PDF-1.4"), max_bytes=10_000)
    vector_store = FakeVectorStore()
    pipeline = IngestionService(
        kb_service,
        FakeUnstructured(elements, error),
        FakeEmbeddings(),
        vector_store,
        chunk_strategy=chunk_strategy,
    )
    return kb_service, kb, doc, pipeline, vector_store


def test_pack_elements_groups_and_keeps_tables() -> None:
    elements = [
        {"type": "NarrativeText", "text": "   ", "metadata": {}},  # dropped: empty
        {"type": "NarrativeText", "text": "short", "metadata": {"page_number": 1}},  # too short
        {
            "type": "NarrativeText",
            "text": "第一段落内容足够长凑字数。" * 3,
            "metadata": {"page_number": 1},
        },
        {
            "type": "NarrativeText",
            "text": "第二段落内容也不短凑字。" * 3,
            "metadata": {"page_number": 2},
        },
        {
            "type": "Table",
            "text": "tiny",
            "metadata": {
                "page_number": 3,
                "text_as_html": "<table><tr><td>总资产</td></tr></table>",
            },
        },  # HTML preferred, table stays standalone
        {"type": "NarrativeText", "text": "x" * 25, "metadata": {"page_number": "4"}},
        "not-a-dict",  # ignored
    ]
    chunks = pack_elements(elements, "a.pdf", max_chars=100)

    assert len(chunks) == 3
    merged = chunks[0]
    assert merged["page_number"] == 1  # page of the first element in the pack
    assert merged["metadata"]["filename"] == "a.pdf"
    assert "第一段落" in merged["text"] and "第二段落" in merged["text"]
    assert chunks[1]["metadata"]["type"] == "Table"
    assert chunks[1]["text"].startswith("<table>")
    assert chunks[1]["page_number"] == 3
    assert chunks[2]["page_number"] == 4  # string page number coerced


def test_pack_elements_soft_limit_starts_new_chunk() -> None:
    paragraphs = [
        {"type": "NarrativeText", "text": "字" * 30, "metadata": {"page_number": i + 1}}
        for i in range(3)
    ]
    chunks = pack_elements(paragraphs, "a.pdf", max_chars=50)  # soft limit 40

    assert len(chunks) == 3  # 30+30 > 40 → each element lands in its own chunk
    assert [chunk["page_number"] for chunk in chunks] == [1, 2, 3]


def test_pack_elements_hard_splits_oversized() -> None:
    elements = [{"type": "NarrativeText", "text": "y" * 250, "metadata": {"page_number": 7}}]
    chunks = pack_elements(elements, "a.pdf", max_chars=100)

    assert [len(chunk["text"]) for chunk in chunks] == [100, 100, 50]
    assert all(chunk["page_number"] == 7 for chunk in chunks)


def test_pack_elements_empty_input() -> None:
    assert pack_elements([{"type": "Image", "text": "", "metadata": {}}], "a.pdf") == []


def element(element_type: str, text: str, page: int, **meta: object) -> dict:
    return {"type": element_type, "text": text, "metadata": {"page_number": page, **meta}}


def test_title_aware_strategy_splits_sections_and_prepends_titles() -> None:
    elements = [
        element("Title", "第一章 总则", 1),
        element("NarrativeText", "总则正文内容，足够长不被丢弃。" * 2, 1),
        element("Title", "第二章 股份", 2),
        element("Table", "tiny", 2, text_as_html="<table><tr><td>股本结构</td></tr></table>"),
        element("NarrativeText", "股份正文，也很长不被丢弃。" * 2, 3),
    ]
    chunks = pack_elements(elements, "a.pdf", strategy="title_aware", max_chars=400)

    assert len(chunks) == 3
    assert chunks[0]["text"].startswith("第一章 总则")
    assert chunks[0]["metadata"]["section"] == "第一章 总则"
    assert chunks[0]["page_number"] == 1
    assert chunks[1]["metadata"]["type"] == "Table"  # table keeps its section prefix
    assert chunks[1]["text"].startswith("第二章 股份")
    assert chunks[2]["metadata"]["section"] == "第二章 股份"


def test_pack_strategy_with_title_context_prepends_nearest_title() -> None:
    elements = [
        element("Title", "第一章 总则", 1),
        element("NarrativeText", "正文内容足够长，单独成块。" * 3, 1),
    ]
    chunks = pack_elements(elements, "a.pdf", strategy="pack", max_chars=200)

    assert len(chunks) == 1
    assert chunks[0]["text"].startswith("第一章 总则\n\n")
    assert chunks[0]["metadata"]["section"] == "第一章 总则"


def test_pack_strategy_without_title_context_keeps_legacy_behaviour() -> None:
    elements = [
        element("Title", "短标题", 1),  # dropped: < min_chars
        element("NarrativeText", "正文内容足够长，单独成块。" * 3, 1),
    ]
    chunks = pack_elements(elements, "a.pdf", strategy="pack", title_context=False)

    assert len(chunks) == 1
    assert "短标题" not in chunks[0]["text"]
    assert "section" not in chunks[0]["metadata"]


def test_element_strategy_maps_one_to_one() -> None:
    elements = [
        element("NarrativeText", "第一段，足够长。" * 3, 1),
        element("NarrativeText", "第二段，也足够长。" * 3, 2),
    ]
    chunks = pack_elements(elements, "a.pdf", strategy="element")

    assert [c["page_number"] for c in chunks] == [1, 2]
    assert all("section" not in c["metadata"] for c in chunks)


def test_pack_elements_overlap_slides_the_window() -> None:
    full = "".join(str(i % 10) for i in range(100))  # "0123456789012…"
    elements = [element("NarrativeText", full, 1)]
    chunks = pack_elements(elements, "a.pdf", strategy="pack", max_chars=60, overlap=20)

    # window = 60, step = 40 → 100 chars land in 3 overlapping pieces
    assert [len(c["text"]) for c in chunks] == [60, 60, 20]
    assert chunks[1]["text"] == full[40:100]  # second window starts at 40
    assert chunks[2]["text"] == full[80:100]


def test_oversized_split_survives_huge_section_prefix() -> None:
    # A title longer than max_chars must not collapse the split window
    # into 1-char pieces (regression: 499 chars were silently lost).
    elements = [
        element("Title", "超" * 900, 1),
        element("NarrativeText", "正" * 500, 1),
    ]
    chunks = pack_elements(elements, "a.pdf", strategy="title_aware", max_chars=300, overlap=0)

    split = [c for c in chunks if c["metadata"]["type"] == "NarrativeText"]
    assert [len(c["text"]) for c in split] == [300, 200]  # full window, no shattering
    assert "".join(c["text"] for c in split) == "正" * 500  # no text lost


def test_unknown_chunk_strategy_raises() -> None:
    import pytest

    with pytest.raises(ValueError, match="unknown chunk strategy"):
        pack_elements([], "a.pdf", strategy="magic")


def test_ingestion_trace_records_chunk_strategy(tmp_path: Path) -> None:
    kb_service, kb, doc, pipeline, _ = make_pipeline(
        tmp_path,
        elements=[element("NarrativeText", "这是一段足够长的中文文本内容，用于入库链路测试。", 1)],
        chunk_strategy="element",
    )
    pipeline.ingest(doc.id)

    events = kb_service.list_pipeline_events(doc.id)
    chunk_event = next(e for e in events if e.stage == "chunk")
    assert json.loads(chunk_event.detail or "{}")["strategy"] == "element"


def test_ingest_happy_path(tmp_path: Path) -> None:
    kb_service, kb, doc, pipeline, vector_store = make_pipeline(
        tmp_path,
        elements=[
            {
                "type": "NarrativeText",
                "text": "这是一段足够长的中文文本内容，用于入库链路测试。",
                "metadata": {"page_number": 1},
            }
        ],
    )
    pipeline.ingest(doc.id)

    final = kb_service.get_document(doc.id)
    assert final is not None
    assert final.status == "ready"
    assert final.chunkCount == 1
    assert vector_store.rows[0]["doc_id"] == doc.id
    assert vector_store.rows[0]["page_number"] == 1
    assert vector_store.rows[0]["dense"] == [0.1, 0.2]
    assert vector_store.rows[0]["metadata"]["filename"] == "manual.pdf"
    assert vector_store.deleted == [(kb.collectionName, doc.id)]  # idempotency pre-clean
    assert vector_store.collections == [kb.collectionName]

    events = kb_service.list_pipeline_events(doc.id)
    assert [(e.stage, e.status) for e in events] == [
        ("parse", "succeeded"),
        ("chunk", "succeeded"),
        ("embed", "succeeded"),
        ("index", "succeeded"),
    ]
    parse_detail = json.loads(events[0].detail or "{}")
    assert parse_detail == {"elements": 1, "source": "api", "profile": "best"}
    assert events[0].durationMs is not None


def test_ingest_marks_failed_when_no_text_extracted(tmp_path: Path) -> None:
    kb_service, _, doc, pipeline, vector_store = make_pipeline(
        tmp_path, elements=[{"type": "Image", "text": "", "metadata": {}}]
    )
    pipeline.ingest(doc.id)

    final = kb_service.get_document(doc.id)
    assert final is not None
    assert final.status == "failed"
    assert final.error is not None and "no extractable text" in final.error
    assert vector_store.rows == []

    events = kb_service.list_pipeline_events(doc.id)
    assert ("parse", "succeeded") in [(e.stage, e.status) for e in events]
    assert ("chunk", "failed") in [(e.stage, e.status) for e in events]


def test_ingest_marks_failed_on_unstructured_error(tmp_path: Path) -> None:
    kb_service, _, doc, pipeline, _ = make_pipeline(tmp_path, error=RuntimeError("boom"))
    pipeline.ingest(doc.id)

    final = kb_service.get_document(doc.id)
    assert final is not None
    assert final.status == "failed"
    assert final.error is not None and "RuntimeError: boom" in final.error


def test_ingest_skips_when_already_processing(tmp_path: Path) -> None:
    kb_service, _, doc, pipeline, vector_store = make_pipeline(
        tmp_path, elements=[{"type": "NarrativeText", "text": "x" * 30, "metadata": {}}]
    )
    kb_service.update_document_status(doc.id, "processing")
    pipeline.ingest(doc.id)

    final = kb_service.get_document(doc.id)
    assert final is not None
    assert final.status == "processing"
    assert vector_store.rows == []


def test_ingest_reuses_parse_and_embed_cache(tmp_path: Path) -> None:
    kb_service = SqliteKnowledgeService(tmp_path / "kb")
    kb = kb_service.create_kb("docs")
    doc = kb_service.save_upload(kb.id, "manual.pdf", io.BytesIO(b"%PDF-1.4"), max_bytes=10_000)
    fake_unstructured = FakeUnstructured(
        [
            {
                "type": "NarrativeText",
                "text": "这是一段足够长的中文文本内容，用于入库链路测试。",
                "metadata": {"page_number": 1},
            }
        ]
    )
    fake_embeddings = FakeEmbeddings()
    vector_store = FakeVectorStore()
    pipeline = IngestionService(
        kb_service,
        fake_unstructured,
        fake_embeddings,
        vector_store,
        cache=PipelineCache(tmp_path / "cache"),
        parse_profile="best",
        embedding_model="BAAI/bge-m3",
        embedding_dim=1024,
    )

    pipeline.ingest(doc.id)
    kb_service.update_document_status(doc.id, "pending", error=None)
    pipeline.ingest(doc.id)  # re-ingest: both paid stages must hit the cache

    assert len(fake_unstructured.calls) == 1
    assert len(fake_embeddings.batches) == 1
    sources = [
        json.loads(e.detail or "{}").get("source")
        for e in kb_service.list_pipeline_events(doc.id)
        if e.stage == "parse"
    ]
    assert sources == ["api", "cache"]
