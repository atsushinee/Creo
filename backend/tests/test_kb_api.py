"""Knowledge base API tests: real SqliteKnowledgeService + stub pipeline.

Follows the existing pattern (tests/test_api.py): wire stubs onto app.state
inside the TestClient context; BackgroundTasks run after each request.
"""

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.kb_service import SqliteKnowledgeService


class RecordingIngestion:
    def __init__(self) -> None:
        self.ingested: list[str] = []

    def ingest(self, doc_id: str) -> None:
        self.ingested.append(doc_id)


class RecordingVectorStore:
    def __init__(self) -> None:
        self.dropped: list[str] = []
        self.deleted: list[tuple[str, str]] = []

    def drop_collection(self, name: str) -> None:
        self.dropped.append(name)

    def delete_doc(self, name: str, doc_id: str) -> None:
        self.deleted.append((name, doc_id))


def wire_knowledge_stack(client: TestClient, tmp_path) -> RecordingIngestion:
    ingestion = RecordingIngestion()
    client.app.state.knowledge_service = SqliteKnowledgeService(tmp_path / "kb")
    client.app.state.ingestion_service = ingestion
    client.app.state.vector_store_service = RecordingVectorStore()
    return ingestion


def test_kb_disabled_returns_503(monkeypatch) -> None:
    from app.core.config import Settings

    monkeypatch.setattr("app.main.get_settings", lambda: Settings(_env_file=None, kb_enabled=False))
    with TestClient(create_app()) as client:
        assert client.get("/api/kb").status_code == 503
        assert client.post("/api/kb", json={"name": "x"}).status_code == 503


def test_kb_crud_and_upload_flow(tmp_path) -> None:
    with TestClient(create_app()) as client:
        ingestion = wire_knowledge_stack(client, tmp_path)

        created = client.post("/api/kb", json={"name": "产品手册", "description": "internal"})
        assert created.status_code == 201
        kb = created.json()
        assert kb["name"] == "产品手册"
        assert kb["documentCount"] == 0
        assert kb["collectionName"].startswith("kb_")

        listing = client.get("/api/kb")
        assert listing.status_code == 200
        assert [item["id"] for item in listing.json()] == [kb["id"]]

        upload = client.post(
            f"/api/kb/{kb['id']}/documents",
            files={"file": ("a.pdf", b"%PDF-1.4 test", "application/pdf")},
        )
        assert upload.status_code == 201
        doc = upload.json()
        assert doc["status"] == "pending"
        assert doc["filename"] == "a.pdf"
        # BackgroundTasks ran after the response: the pipeline saw the upload.
        assert ingestion.ingested == [doc["id"]]

        documents = client.get(f"/api/kb/{kb['id']}/documents")
        assert [item["id"] for item in documents.json()] == [doc["id"]]

        assert kb["documentCount"] == 0  # snapshot taken before the upload
        refreshed = client.get("/api/kb").json()[0]
        assert refreshed["documentCount"] == 1

        duplicate = client.post(
            f"/api/kb/{kb['id']}/documents",
            files={"file": ("a.pdf", b"%PDF-1.4 test", "application/pdf")},
        )
        assert duplicate.status_code == 409

        not_pdf = client.post(
            f"/api/kb/{kb['id']}/documents",
            files={"file": ("a.txt", b"hello", "text/plain")},
        )
        assert not_pdf.status_code == 422

        missing_kb = client.post(
            "/api/kb/nope/documents",
            files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert missing_kb.status_code == 404


def test_delete_document_and_kb(tmp_path) -> None:
    with TestClient(create_app()) as client:
        ingestion = wire_knowledge_stack(client, tmp_path)
        kb = client.post("/api/kb", json={"name": "docs"}).json()
        doc = client.post(
            f"/api/kb/{kb['id']}/documents",
            files={"file": ("a.pdf", b"%PDF-1.4 test", "application/pdf")},
        ).json()

        assert client.delete(f"/api/kb/{kb['id']}/documents/{doc['id']}").status_code == 204
        assert client.app.state.vector_store_service.deleted == [(kb["collectionName"], doc["id"])]
        assert client.get(f"/api/kb/{kb['id']}/documents").json() == []
        assert ingestion.ingested == [doc["id"]]

        assert client.post(
            f"/api/kb/{kb['id']}/documents",
            files={"file": ("b.pdf", b"%PDF-1.4 other", "application/pdf")},
        ).status_code == 201

        assert client.delete(f"/api/kb/{kb['id']}").status_code == 204
        assert client.app.state.vector_store_service.dropped == [kb["collectionName"]]
        assert client.get("/api/kb").json() == []
        assert client.delete(f"/api/kb/{kb['id']}").status_code == 404


def test_reingest_and_processing_guards(tmp_path) -> None:
    with TestClient(create_app()) as client:
        wire_knowledge_stack(client, tmp_path)
        kb = client.post("/api/kb", json={"name": "docs"}).json()

        missing = client.post(f"/api/kb/{kb['id']}/documents/none/reingest")
        assert missing.status_code == 404

        doc = client.post(
            f"/api/kb/{kb['id']}/documents",
            files={"file": ("a.pdf", b"%PDF-1.4 test", "application/pdf")},
        ).json()

        reingest = client.post(f"/api/kb/{kb['id']}/documents/{doc['id']}/reingest")
        assert reingest.status_code == 202
        assert reingest.json()["status"] == "pending"

        # Simulate a running pipeline: both destructive operations must refuse.
        service = client.app.state.knowledge_service
        service.update_document_status(doc["id"], "processing")
        assert client.delete(f"/api/kb/{kb['id']}/documents/{doc['id']}").status_code == 409
        assert client.post(f"/api/kb/{kb['id']}/documents/{doc['id']}/reingest").status_code == 409
