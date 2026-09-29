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
) -> tuple[SqliteKnowledgeService, KnowledgeBase, KbDocument, IngestionService, FakeVectorStore]:
    kb_service = SqliteKnowledgeService(tmp_path / "kb")
    kb = kb_service.create_kb("docs")
    doc = kb_service.save_upload(kb.id, "manual.pdf", io.BytesIO(b"%PDF-1.4"), max_bytes=10_000)
    vector_store = FakeVectorStore()
    pipeline = IngestionService(
        kb_service, FakeUnstructured(elements, error), FakeEmbeddings(), vector_store
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
