"""Persistence guarantees: sessions survive restarts, interrupted ingests
recover, and the Milvus connection is never dialed at startup.
"""

import io

import pytest
from pymilvus.exceptions import MilvusException

from app.services.kb_service import SqliteKnowledgeService
from app.services.kb_vector_store import MilvusVectorStore
from app.services.session_service import SqliteSessionService


def test_sqlite_sessions_survive_reinstall(tmp_path) -> None:
    db_path = tmp_path / "sessions.sqlite"
    service = SqliteSessionService(db_path)
    service.ensure("sess-2")
    service.ensure("sess-1")
    service.touch("sess-1", title="hello world")  # strictly later than sess-2

    # A "restarted" backend opens the same database file fresh.
    reopened = SqliteSessionService(db_path)
    listing = reopened.list()
    assert [s.id for s in listing] == ["sess-1", "sess-2"]  # newest first
    assert listing[0].title == "hello world"

    assert reopened.delete("sess-1") is True
    assert reopened.get("sess-1") is None
    service.close()
    reopened.close()


def test_fail_interrupted_ingestions_marks_stale_processing(tmp_path) -> None:
    service = SqliteKnowledgeService(tmp_path / "kb")
    kb = service.create_kb("docs")
    doc = service.save_upload(kb.id, "a.pdf", io.BytesIO(b"%PDF"), max_bytes=1024)
    service.update_document_status(doc.id, "processing")
    other = service.save_upload(kb.id, "b.pdf", io.BytesIO(b"%PDF2"), max_bytes=1024)
    service.update_document_status(other.id, "ready")

    marked = service.fail_interrupted_ingestions()

    assert marked == 1
    failed = service.get_document(doc.id)
    assert failed is not None
    assert failed.status == "failed"
    assert failed.error is not None and "restarted" in failed.error
    ready = service.get_document(other.id)
    assert ready is not None and ready.status == "ready"
    assert service.fail_interrupted_ingestions() == 0  # idempotent


def test_milvus_store_constructor_does_not_dial(tmp_path) -> None:
    # The connection must be lazy: constructing the store with an unreachable
    # URI succeeds (startup never depends on the vector database being up).
    store = MilvusVectorStore("http://127.0.0.1:1", token="x", dim=1024)
    assert store._client is None  # not connected yet

    # First real use attempts the connection; against a dead endpoint it
    # fails loudly — but only that operation fails, not the whole KB stack.
    with pytest.raises(MilvusException):
        store.has_collection("anything")
    # A failed attempt leaves no half-initialized client; the next call retries.
    assert store._client is None
