"""SqliteKnowledgeService: registry + file storage (tmp_path isolated)."""

import io

import pytest

from app.services.kb_service import (
    DuplicateDocumentError,
    SqliteKnowledgeService,
    UploadTooLargeError,
    collection_name_for,
)


def make_service(tmp_path) -> SqliteKnowledgeService:
    return SqliteKnowledgeService(tmp_path / "kb-root")


def test_create_kb_and_collection_name(tmp_path) -> None:
    service = make_service(tmp_path)
    kb = service.create_kb("产品手册", "user docs")
    assert kb.collectionName.startswith("kb_")  # non-ascii name falls back to the kb slug
    assert kb.collectionName.endswith(kb.id[:8])
    assert (tmp_path / "kb-root" / kb.id / "files").is_dir()
    assert service.get_kb(kb.id) is not None
    assert [k.id for k in service.list_kbs()] == [kb.id]
    assert service.count_documents(kb.id) == 0


def test_collection_name_for_sanitizes() -> None:
    assert collection_name_for("My Manuals!!", "abcdef123456") == "my_manuals_abcdef12"
    assert collection_name_for("产品", "abcdef123456") == "kb_abcdef12"
    assert collection_name_for("9reports", "abcdef123456") == "kb_9reports_abcdef12"


def test_save_upload_writes_file_and_dedupes(tmp_path) -> None:
    service = make_service(tmp_path)
    kb = service.create_kb("docs")
    payload = b"%PDF-1.4 fake"
    doc = service.save_upload(kb.id, "manual.pdf", io.BytesIO(payload), max_bytes=1024)
    assert doc.status == "pending"
    assert doc.size == len(payload)
    assert len(doc.sha256) == 64
    path = service.document_path(doc)
    assert path.is_file() and path.read_bytes() == payload
    assert service.list_documents(kb.id)[0].id == doc.id

    with pytest.raises(DuplicateDocumentError):
        service.save_upload(kb.id, "manual.pdf", io.BytesIO(payload), max_bytes=1024)
    assert service.count_documents(kb.id) == 1
    assert path.is_file()  # the original upload survives a rejected duplicate


def test_save_upload_rejects_oversize(tmp_path) -> None:
    service = make_service(tmp_path)
    kb = service.create_kb("docs")
    with pytest.raises(UploadTooLargeError):
        service.save_upload(kb.id, "big.pdf", io.BytesIO(b"x" * 100), max_bytes=10)
    assert service.count_documents(kb.id) == 0


def test_save_upload_requires_existing_kb(tmp_path) -> None:
    service = make_service(tmp_path)
    with pytest.raises(KeyError):
        service.save_upload("missing", "a.pdf", io.BytesIO(b"%PDF"), max_bytes=1024)


def test_delete_kb_purges_documents_and_events(tmp_path) -> None:
    service = make_service(tmp_path)
    kb = service.create_kb("docs")
    doc = service.save_upload(kb.id, "a.pdf", io.BytesIO(b"%PDF"), max_bytes=1024)
    service.add_pipeline_event(doc.id, kb.id, "upload", "succeeded")

    assert service.delete_kb(kb.id) is True

    assert service.count_documents(kb.id) == 0
    assert service.get_document(doc.id) is None
    assert service.list_pipeline_events(doc.id) == []
    assert not (tmp_path / "kb-root" / kb.id).exists()


def test_pipeline_events_roundtrip(tmp_path) -> None:
    service = make_service(tmp_path)
    kb = service.create_kb("docs")
    doc = service.save_upload(kb.id, "a.pdf", io.BytesIO(b"%PDF"), max_bytes=1024)

    event = service.add_pipeline_event(
        doc.id, kb.id, "parse", "succeeded", detail='{"elements": 3}', duration_ms=120
    )
    service.add_pipeline_event(doc.id, kb.id, "embed", "failed", detail='{"error": "boom"}')

    events = service.list_pipeline_events(doc.id)
    assert [e.stage for e in events] == ["parse", "embed"]
    assert events[0].id == event.id
    assert events[0].durationMs == 120
    assert events[0].detail == '{"elements": 3}'
    assert events[1].status == "failed"

    assert service.delete_document(doc.id) is True
    assert service.list_pipeline_events(doc.id) == []


def test_status_transitions_and_delete(tmp_path) -> None:
    service = make_service(tmp_path)
    kb = service.create_kb("docs")
    doc = service.save_upload(kb.id, "a.pdf", io.BytesIO(b"%PDF"), max_bytes=1024)

    service.update_document_status(doc.id, "processing")
    service.update_document_status(doc.id, "failed", error="boom")
    failed = service.get_document(doc.id)
    assert failed is not None
    assert failed.status == "failed"
    assert failed.error == "boom"

    assert service.delete_document(doc.id) is True
    assert service.get_document(doc.id) is None
    assert not service.document_path(doc).exists()

    assert service.delete_kb(kb.id) is True
    assert service.get_kb(kb.id) is None
    assert not (tmp_path / "kb-root" / kb.id).exists()
