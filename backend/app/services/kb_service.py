"""Knowledge base storage boundary (ADR-0004).

The interface (KnowledgeService) isolates storage: the current implementation
is a stdlib SQLite registry plus on-disk files under one data directory; a
real DB can replace it later without touching routes, pipeline or tools
(docs/architecture.md §7).
"""

import hashlib
import re
import shutil
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.models.knowledge import KbDocumentStatus

logger = get_logger("services.kb")

_SLUG_MAX = 32


class DuplicateDocumentError(Exception):
    """An identical file (same sha256) already exists in the knowledge base."""


class UploadTooLargeError(Exception):
    """The upload exceeds the configured size limit."""


def collection_name_for(name: str, kb_id: str) -> str:
    """Milvus collection name: ASCII slug of the KB name + short unique suffix."""
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()[:_SLUG_MAX].strip("_")
    if not slug:
        slug = "kb"
    if not slug[0].isalpha():
        slug = f"kb_{slug}"
    return f"{slug}_{kb_id[:8]}"[:64]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class KnowledgeBase(BaseModel):
    id: str
    name: str
    description: str = ""
    collectionName: str
    createdAt: datetime = Field(default_factory=_utcnow)


class KbDocument(BaseModel):
    id: str
    kbId: str
    filename: str
    path: str  # relative to the KB data dir, e.g. "{kb_id}/files/{disk_name}"
    size: int = 0
    sha256: str = ""
    status: KbDocumentStatus = "pending"
    error: str | None = None
    chunkCount: int = 0
    createdAt: datetime = Field(default_factory=_utcnow)
    updatedAt: datetime = Field(default_factory=_utcnow)


class PipelineEvent(BaseModel):
    """One recorded pipeline stage for a document (trace/audit, ADR-0004)."""

    id: int
    docId: str
    kbId: str
    stage: str  # upload | parse | chunk | embed | index
    status: str  # started | succeeded | failed
    detail: str | None = None  # JSON payload (counts, durations, errors)
    durationMs: int | None = None
    createdAt: datetime = Field(default_factory=_utcnow)


class KnowledgeService(Protocol):
    """Storage-agnostic knowledge base + document registry."""

    def create_kb(self, name: str, description: str = "") -> KnowledgeBase: ...
    def list_kbs(self) -> list[KnowledgeBase]: ...
    def get_kb(self, kb_id: str) -> KnowledgeBase | None: ...
    def delete_kb(self, kb_id: str) -> bool: ...
    def save_upload(
        self, kb_id: str, filename: str, stream: BinaryIO, *, max_bytes: int
    ) -> KbDocument: ...
    def list_documents(self, kb_id: str) -> list[KbDocument]: ...
    def get_document(self, doc_id: str) -> KbDocument | None: ...
    def update_document_status(
        self,
        doc_id: str,
        status: KbDocumentStatus,
        *,
        error: str | None = None,
        chunk_count: int | None = None,
    ) -> KbDocument | None: ...
    def delete_document(self, doc_id: str) -> bool: ...
    def document_path(self, doc: KbDocument) -> Path: ...
    def count_documents(self, kb_id: str) -> int: ...
    def add_pipeline_event(
        self,
        doc_id: str,
        kb_id: str,
        stage: str,
        status: str,
        *,
        detail: str | None = None,
        duration_ms: int | None = None,
    ) -> PipelineEvent: ...
    def list_pipeline_events(self, doc_id: str) -> list[PipelineEvent]: ...


_SCHEMA = """
CREATE TABLE IF NOT EXISTS kb (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    collection_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS document (
    id TEXT PRIMARY KEY,
    kb_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    path TEXT NOT NULL,
    size INTEGER NOT NULL DEFAULT 0,
    sha256 TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    error TEXT,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_document_kb ON document(kb_id);
CREATE TABLE IF NOT EXISTS pipeline_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL,
    kb_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT,
    duration_ms INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pipeline_event_doc ON pipeline_event(doc_id);
"""


def _safe_filename(filename: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", Path(filename).name).strip()
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    stem = name[:-4][:110] or "document"
    return f"{stem}.pdf"


def _row_to_kb(row: sqlite3.Row) -> KnowledgeBase:
    return KnowledgeBase(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        collectionName=row["collection_name"],
        createdAt=datetime.fromisoformat(row["created_at"]),
    )


def _row_to_doc(row: sqlite3.Row) -> KbDocument:
    return KbDocument(
        id=row["id"],
        kbId=row["kb_id"],
        filename=row["filename"],
        path=row["path"],
        size=row["size"],
        sha256=row["sha256"],
        status=row["status"],
        error=row["error"],
        chunkCount=row["chunk_count"],
        createdAt=datetime.fromisoformat(row["created_at"]),
        updatedAt=datetime.fromisoformat(row["updated_at"]),
    )


class SqliteKnowledgeService:
    """Thread-safe SQLite + filesystem KnowledgeService (swap for a real DB later)."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._lock = threading.Lock()
        data_dir.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(data_dir / "kb.sqlite", check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # --- knowledge bases -----------------------------------------------------

    def create_kb(self, name: str, description: str = "") -> KnowledgeBase:
        kb_id = uuid4().hex
        kb = KnowledgeBase(
            id=kb_id,
            name=name,
            description=description,
            collectionName=collection_name_for(name, kb_id),
        )
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO kb (id, name, description, collection_name, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (kb.id, kb.name, kb.description, kb.collectionName, kb.createdAt.isoformat()),
            )
        (self._data_dir / kb.id / "files").mkdir(parents=True, exist_ok=True)
        logger.info(
            "created knowledge base id=%s name=%s collection=%s",
            kb.id,
            kb.name,
            kb.collectionName,
        )
        return kb

    def list_kbs(self) -> list[KnowledgeBase]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM kb ORDER BY created_at DESC").fetchall()
        return [_row_to_kb(row) for row in rows]

    def get_kb(self, kb_id: str) -> KnowledgeBase | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM kb WHERE id = ?", (kb_id,)).fetchone()
        return _row_to_kb(row) if row is not None else None

    def delete_kb(self, kb_id: str) -> bool:
        with self._lock, self._conn:
            cursor = self._conn.execute("DELETE FROM kb WHERE id = ?", (kb_id,))
            self._conn.execute("DELETE FROM document WHERE kb_id = ?", (kb_id,))
            self._conn.execute("DELETE FROM pipeline_event WHERE kb_id = ?", (kb_id,))
        shutil.rmtree(self._data_dir / kb_id, ignore_errors=True)
        return cursor.rowcount > 0

    # --- documents ------------------------------------------------------------

    def save_upload(
        self, kb_id: str, filename: str, stream: BinaryIO, *, max_bytes: int
    ) -> KbDocument:
        if self.get_kb(kb_id) is None:
            raise KeyError(f"knowledge base not found: {kb_id}")
        doc_id = uuid4().hex
        disk_name = _safe_filename(filename)
        # doc_id prefix keeps same-named uploads in one KB from clobbering
        # each other on disk.
        rel_path = f"{kb_id}/files/{doc_id}__{disk_name}"
        destination = self._data_dir / rel_path
        destination.parent.mkdir(parents=True, exist_ok=True)

        digest = hashlib.sha256()
        size = 0
        try:
            with destination.open("wb") as out:
                while chunk := stream.read(1 << 20):
                    size += len(chunk)
                    if size > max_bytes:
                        raise UploadTooLargeError(f"file exceeds {max_bytes} bytes")
                    digest.update(chunk)
                    out.write(chunk)
        except BaseException:
            destination.unlink(missing_ok=True)
            raise

        sha256 = digest.hexdigest()
        now = _utcnow().isoformat()
        with self._lock, self._conn:
            duplicate = self._conn.execute(
                "SELECT id FROM document WHERE kb_id = ? AND sha256 = ?", (kb_id, sha256)
            ).fetchone()
            if duplicate is not None:
                destination.unlink(missing_ok=True)
                raise DuplicateDocumentError(
                    f"identical file already uploaded to knowledge base {kb_id}"
                )
            self._conn.execute(
                "INSERT INTO document (id, kb_id, filename, path, size, sha256, status,"
                " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
                (doc_id, kb_id, filename, rel_path, size, sha256, now, now),
            )
        logger.info("saved upload doc=%s kb=%s file=%s size=%d", doc_id, kb_id, disk_name, size)
        document = self.get_document(doc_id)
        assert document is not None  # inserted above within the same process
        return document

    def list_documents(self, kb_id: str) -> list[KbDocument]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM document WHERE kb_id = ? ORDER BY created_at DESC", (kb_id,)
            ).fetchall()
        return [_row_to_doc(row) for row in rows]

    def get_document(self, doc_id: str) -> KbDocument | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM document WHERE id = ?", (doc_id,)).fetchone()
        return _row_to_doc(row) if row is not None else None

    def update_document_status(
        self,
        doc_id: str,
        status: KbDocumentStatus,
        *,
        error: str | None = None,
        chunk_count: int | None = None,
    ) -> KbDocument | None:
        assignments = ["status = ?", "error = ?", "updated_at = ?"]
        values: list[object] = [status, error, _utcnow().isoformat()]
        if chunk_count is not None:
            assignments.append("chunk_count = ?")
            values.append(chunk_count)
        values.append(doc_id)
        with self._lock, self._conn:
            self._conn.execute(
                f"UPDATE document SET {', '.join(assignments)} WHERE id = ?", values
            )
        return self.get_document(doc_id)

    def delete_document(self, doc_id: str) -> bool:
        document = self.get_document(doc_id)
        if document is None:
            return False
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM document WHERE id = ?", (doc_id,))
            self._conn.execute("DELETE FROM pipeline_event WHERE doc_id = ?", (doc_id,))
        (self._data_dir / document.path).unlink(missing_ok=True)
        return True

    def document_path(self, doc: KbDocument) -> Path:
        return self._data_dir / doc.path

    def count_documents(self, kb_id: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM document WHERE kb_id = ?", (kb_id,)
            ).fetchone()
        return int(row["n"]) if row is not None else 0

    # --- pipeline trace -------------------------------------------------------

    def add_pipeline_event(
        self,
        doc_id: str,
        kb_id: str,
        stage: str,
        status: str,
        *,
        detail: str | None = None,
        duration_ms: int | None = None,
    ) -> PipelineEvent:
        created = _utcnow().isoformat()
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "INSERT INTO pipeline_event (doc_id, kb_id, stage, status, detail,"
                " duration_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (doc_id, kb_id, stage, status, detail, duration_ms, created),
            )
        return PipelineEvent(
            id=int(cursor.lastrowid or 0),
            docId=doc_id,
            kbId=kb_id,
            stage=stage,
            status=status,
            detail=detail,
            durationMs=duration_ms,
            createdAt=datetime.fromisoformat(created),
        )

    def list_pipeline_events(self, doc_id: str) -> list[PipelineEvent]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM pipeline_event WHERE doc_id = ? ORDER BY id ASC", (doc_id,)
            ).fetchall()
        return [
            PipelineEvent(
                id=row["id"],
                docId=row["doc_id"],
                kbId=row["kb_id"],
                stage=row["stage"],
                status=row["status"],
                detail=row["detail"],
                durationMs=row["duration_ms"],
                createdAt=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def close(self) -> None:
        self._conn.close()
