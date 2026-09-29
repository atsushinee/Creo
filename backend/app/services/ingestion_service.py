"""Ingestion pipeline (ADR-0004): PDF → Unstructured → chunk normalization →
dense embeddings → Milvus insert (sparse BM25 is derived server-side).

Runs synchronously on a worker thread — FastAPI BackgroundTasks executes sync
callables via its threadpool. Document status lives in the KnowledgeService so
the frontend can poll it.
"""

from pathlib import Path
from typing import Any, Protocol

from app.core.logging import get_logger
from app.services.kb_service import KnowledgeService

logger = get_logger("services.ingestion")

MIN_CHUNK_CHARS = 20
MAX_CHUNK_CHARS = 60_000  # stay well under the Milvus VARCHAR limit


class IngestionError(RuntimeError):
    """The document cannot be ingested (mapped to a failed status)."""


class UnstructuredClientLike(Protocol):
    def partition_pdf(self, path: Path, filename: str) -> list[dict]: ...


class EmbeddingClientLike(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class VectorStoreLike(Protocol):
    def ensure_collection(self, name: str) -> None: ...
    def insert_chunks(self, name: str, rows: list[dict[str, Any]]) -> int: ...
    def delete_doc(self, name: str, doc_id: str) -> None: ...


def normalize_elements(
    elements: list[dict],
    filename: str,
    *,
    min_chars: int = MIN_CHUNK_CHARS,
) -> list[dict[str, Any]]:
    """Map raw Unstructured elements to index rows.

    Drops empty/too-short chunks, prefers table HTML for Table elements and
    keeps page numbers for citations.
    """
    chunks: list[dict[str, Any]] = []
    for element in elements:
        if not isinstance(element, dict):
            continue
        text = str(element.get("text") or "").strip()
        meta = element.get("metadata")
        if not isinstance(meta, dict):
            meta = {}
        if element.get("type") == "Table":
            html = meta.get("text_as_html")
            if isinstance(html, str) and len(html.strip()) > len(text):
                text = html.strip()
        if len(text) < min_chars:
            continue
        try:
            page = int(meta.get("page_number") or 0)
        except (TypeError, ValueError):
            page = 0
        chunks.append(
            {
                "text": text[:MAX_CHUNK_CHARS],
                "page_number": page,
                "metadata": {"type": str(element.get("type") or ""), "filename": filename},
            }
        )
    return chunks


class IngestionService:
    """Orchestrates one document's path from stored file to searchable vectors."""

    def __init__(
        self,
        knowledge_service: KnowledgeService,
        unstructured: UnstructuredClientLike,
        embeddings: EmbeddingClientLike,
        vector_store: VectorStoreLike,
    ) -> None:
        self._knowledge = knowledge_service
        self._unstructured = unstructured
        self._embeddings = embeddings
        self._vector = vector_store

    def ingest(self, doc_id: str) -> None:
        """Process one document; never raises — failures land on the doc row."""
        doc = self._knowledge.get_document(doc_id)
        if doc is None:
            logger.warning("ingest skipped: unknown document %s", doc_id)
            return
        kb = self._knowledge.get_kb(doc.kbId)
        if kb is None:
            self._knowledge.update_document_status(doc_id, "failed", error="knowledge base gone")
            return
        if doc.status == "processing":
            logger.info("ingest skipped: document %s already processing", doc_id)
            return

        self._knowledge.update_document_status(doc_id, "processing")
        try:
            elements = self._unstructured.partition_pdf(
                self._knowledge.document_path(doc), doc.filename
            )
            chunks = normalize_elements(elements, doc.filename)
            if not chunks:
                raise IngestionError(
                    "no extractable text (scanned PDF? check strategy/OCR languages)"
                )
            vectors = self._embeddings.embed_texts([chunk["text"] for chunk in chunks])
            rows = [
                {
                    "text": chunk["text"],
                    "dense": vector,
                    "doc_id": doc.id,
                    "chunk_index": index,
                    "page_number": min(max(chunk["page_number"], 0), 32_767),
                    "metadata": chunk["metadata"],
                }
                for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
            ]
            self._vector.ensure_collection(kb.collectionName)
            self._vector.delete_doc(kb.collectionName, doc.id)  # idempotent re-ingest
            self._vector.insert_chunks(kb.collectionName, rows)
            self._knowledge.update_document_status(doc_id, "ready", chunk_count=len(rows))
            logger.info(
                "ingested document=%s chunks=%d collection=%s", doc.id, len(rows), kb.collectionName
            )
        except Exception as exc:
            logger.exception("ingestion failed for document=%s", doc_id)
            self._knowledge.update_document_status(
                doc_id, "failed", error=f"{type(exc).__name__}: {exc}"
            )
