"""Ingestion pipeline (ADR-0004, updated): PDF → Unstructured Transform API →
element packing (client-side chunking) → dense embeddings → Milvus insert
(sparse BM25 is derived server-side).

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
    def parse_pdf(self, path: Path, filename: str) -> list[dict]: ...


class EmbeddingClientLike(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class VectorStoreLike(Protocol):
    def ensure_collection(self, name: str) -> None: ...
    def insert_chunks(self, name: str, rows: list[dict[str, Any]]) -> int: ...
    def delete_doc(self, name: str, doc_id: str) -> None: ...


def pack_elements(
    elements: list[dict],
    filename: str,
    *,
    max_chars: int = 1500,
    min_chars: int = MIN_CHUNK_CHARS,
) -> list[dict[str, Any]]:
    """Group consecutive Unstructured elements into retrieval chunks.

    The Transform API returns un-chunked elements, so chunking happens here
    (the old by_title behaviour moved client-side): tables stay standalone
    with their HTML projection, narrative elements are greedily packed up to a
    soft limit (~80% of max_chars), single oversized elements are hard-split,
    and too-short fragments are dropped. Page numbers come from the first
    element of each chunk.
    """
    prepared: list[dict[str, Any]] = []
    for element in elements:
        if not isinstance(element, dict):
            continue
        text = str(element.get("text") or "").strip()
        meta = element.get("metadata") if isinstance(element.get("metadata"), dict) else {}
        is_table = element.get("type") == "Table"
        if is_table:
            html = meta.get("text_as_html")
            if isinstance(html, str) and len(html.strip()) > len(text):
                text = html.strip()
        if len(text) < min_chars:
            continue
        try:
            page = int(meta.get("page_number") or 0)
        except (TypeError, ValueError):
            page = 0
        prepared.append(
            {
                "text": text[:MAX_CHUNK_CHARS],
                "page": page,
                "type": str(element.get("type") or ""),
                "is_table": is_table,
            }
        )

    soft_limit = max(min_chars, int(max_chars * 0.8))
    chunks: list[dict[str, Any]] = []
    buffer: list[str] = []
    buffer_len = 0
    buffer_page = 0
    buffer_type = ""

    def flush() -> None:
        nonlocal buffer, buffer_len
        if not buffer:
            return
        chunks.append(
            {
                "text": "\n\n".join(buffer),
                "page_number": buffer_page,
                "metadata": {"type": buffer_type, "filename": filename},
            }
        )
        buffer, buffer_len = [], 0

    for item in prepared:
        if item["is_table"]:
            flush()
            chunks.append(
                {
                    "text": item["text"],
                    "page_number": item["page"],
                    "metadata": {"type": "Table", "filename": filename},
                }
            )
            continue
        if buffer and buffer_len + len(item["text"]) > soft_limit:
            flush()
        if not buffer:
            buffer_page = item["page"]
            buffer_type = item["type"]
        if len(item["text"]) > max_chars:
            flush()
            for start in range(0, len(item["text"]), max_chars):
                piece = item["text"][start : start + max_chars]
                if start == 0 or len(piece) >= min_chars:
                    chunks.append(
                        {
                            "text": piece,
                            "page_number": item["page"],
                            "metadata": {"type": item["type"], "filename": filename},
                        }
                    )
            continue
        buffer.append(item["text"])
        buffer_len += len(item["text"])
    flush()
    return chunks


class IngestionService:
    """Orchestrates one document's path from stored file to searchable vectors."""

    def __init__(
        self,
        knowledge_service: KnowledgeService,
        unstructured: UnstructuredClientLike,
        embeddings: EmbeddingClientLike,
        vector_store: VectorStoreLike,
        *,
        max_chars: int = 1500,
    ) -> None:
        self._knowledge = knowledge_service
        self._unstructured = unstructured
        self._embeddings = embeddings
        self._vector = vector_store
        self._max_chars = max_chars

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
            elements = self._unstructured.parse_pdf(
                self._knowledge.document_path(doc), doc.filename
            )
            chunks = pack_elements(elements, doc.filename, max_chars=self._max_chars)
            if not chunks:
                raise IngestionError("no extractable text (scanned PDF? try profile=best)")
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
