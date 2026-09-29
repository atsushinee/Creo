"""IngestionService orchestration with fake clients (ADR-0004)."""

import io
from pathlib import Path
from typing import Any

from app.services.ingestion_service import IngestionService, normalize_elements
from app.services.kb_service import KbDocument, KnowledgeBase, SqliteKnowledgeService


class FakeUnstructured:
    def __init__(self, elements: list[dict] | None = None, error: Exception | None = None):
        self.elements = elements or []
        self.error = error
        self.calls: list[tuple[Path, str]] = []

    def partition_pdf(self, path: Path, filename: str) -> list[dict]:
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
    tmp_path: Path, elements: list[dict] | None = None, error: Exception | None = None
) -> tuple[SqliteKnowledgeService, KnowledgeBase, KbDocument, IngestionService, FakeVectorStore]:
    kb_service = SqliteKnowledgeService(tmp_path / "kb")
    kb = kb_service.create_kb("docs")
    doc = kb_service.save_upload(kb.id, "manual.pdf", io.BytesIO(b"%PDF-1.4"), max_bytes=10_000)
    vector_store = FakeVectorStore()
    pipeline = IngestionService(
        kb_service, FakeUnstructured(elements, error), FakeEmbeddings(), vector_store
    )
    return kb_service, kb, doc, pipeline, vector_store


def test_normalize_elements() -> None:
    elements = [
        {"type": "NarrativeText", "text": "   ", "metadata": {}},  # dropped: empty
        {"type": "NarrativeText", "text": "short", "metadata": {"page_number": 1}},  # too short
        {
            "type": "Table",
            "text": "tiny",
            "metadata": {
                "page_number": 3,
                "text_as_html": "<table><tr><td>总资产</td></tr></table>",
            },
        },  # HTML preferred over the tiny plain text
        {"type": "NarrativeText", "text": "x" * 25, "metadata": {"page_number": "4"}},
        "not-a-dict",  # ignored
    ]
    chunks = normalize_elements(elements, "a.pdf")
    assert len(chunks) == 2
    assert chunks[0]["metadata"]["type"] == "Table"
    assert chunks[0]["text"].startswith("<table>")
    assert chunks[0]["page_number"] == 3
    assert chunks[0]["metadata"]["filename"] == "a.pdf"
    assert chunks[1]["page_number"] == 4


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
