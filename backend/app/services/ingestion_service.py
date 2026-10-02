"""Ingestion pipeline (ADR-0004, updated): PDF → Unstructured Transform API →
chunking (configurable strategies) → dense embeddings → Milvus insert (sparse
BM25 is derived server-side).

Runs synchronously on a worker thread — FastAPI BackgroundTasks executes sync
callables via its threadpool. Document status lives in the KnowledgeService so
the frontend can poll it. Every stage writes a pipeline_event (trace) and the
paid stages (parse, embed) consult the content-addressed PipelineCache, so a
failed re-run never re-spends API quota for completed stages.
"""

import json
import time
from pathlib import Path
from typing import Any, Protocol

from app.core.logging import get_logger
from app.services.kb_service import KnowledgeService
from app.services.pipeline_cache import PipelineCache

logger = get_logger("services.ingestion")

MIN_CHUNK_CHARS = 20
MAX_CHUNK_CHARS = 60_000  # stay well under the Milvus VARCHAR limit
CHUNK_STRATEGIES = ("pack", "title_aware", "element")
_TITLE_TYPES = ("Title", "Header")


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
    strategy: str = "pack",
    max_chars: int = 1500,
    min_chars: int = MIN_CHUNK_CHARS,
    title_context: bool = True,
    overlap: int = 0,
) -> list[dict[str, Any]]:
    """Chunk Unstructured elements (configurable strategy, ADR-0004 Update 6).

    - ``pack``       greedy packing of consecutive elements (default)
    - ``title_aware`` like pack, but Title/Header elements force a new chunk
    - ``element``    one chunk per element, no packing

    Shared behaviour: tables stay standalone with their HTML projection;
    oversized elements are hard-split (sliding window with `overlap` chars);
    with `title_context` the nearest preceding Title/Header is prepended to
    every chunk (the "merge title" pattern) and recorded in chunk metadata
    as `section`. Page numbers come from the first element of each chunk.
    """
    if strategy not in CHUNK_STRATEGIES:
        raise ValueError(f"unknown chunk strategy: {strategy!r}")
    prepared: list[dict[str, Any]] = []
    for element in elements:
        if not isinstance(element, dict):
            continue
        text = str(element.get("text") or "").strip()
        meta = element.get("metadata") if isinstance(element.get("metadata"), dict) else {}
        element_type = str(element.get("type") or "")
        is_table = element_type == "Table"
        is_title = element_type in _TITLE_TYPES
        if is_table:
            html = meta.get("text_as_html")
            if isinstance(html, str) and len(html.strip()) > len(text):
                text = html.strip()
        if len(text) < min_chars and not (title_context and is_title):
            continue
        try:
            page = int(meta.get("page_number") or 0)
        except (TypeError, ValueError):
            page = 0
        prepared.append(
            {
                "text": text[:MAX_CHUNK_CHARS],
                "page": page,
                "type": element_type,
                "is_table": is_table,
                "is_title": is_title,
            }
        )

    if strategy == "element":
        return _chunk_per_element(prepared, filename)
    return _pack_chunks(
        prepared,
        filename,
        max_chars=max_chars,
        min_chars=min_chars,
        title_context=title_context,
        split_on_titles=strategy == "title_aware",
        overlap=max(0, overlap),
    )


def _pack_chunks(
    prepared: list[dict[str, Any]],
    filename: str,
    *,
    max_chars: int,
    min_chars: int,
    title_context: bool,
    split_on_titles: bool,
    overlap: int,
) -> list[dict[str, Any]]:
    soft_limit = max(1, int(max_chars * 0.8))
    chunks: list[dict[str, Any]] = []
    buffer: list[str] = []
    buffer_len = 0
    buffer_page = 0
    buffer_type = ""
    section = ""

    def flush() -> None:
        nonlocal buffer, buffer_len
        if not buffer:
            return
        text = "\n\n".join(buffer)
        prefix = f"{section}\n\n" if title_context and section else ""
        chunks.append(
            {
                "text": (prefix + text)[:MAX_CHUNK_CHARS],
                "page_number": buffer_page,
                "metadata": {
                    "type": buffer_type,
                    "filename": filename,
                    **({"section": section} if section else {}),
                },
            }
        )
        buffer, buffer_len = [], 0

    def table_chunk(item: dict[str, Any]) -> None:
        prefix = f"{section}\n\n" if title_context and section else ""
        extra = {"section": section} if section else {}
        chunks.append(
            {
                "text": (prefix + item["text"])[:MAX_CHUNK_CHARS],
                "page_number": item["page"],
                "metadata": {"type": "Table", "filename": filename, **extra},
            }
        )

    for item in prepared:
        if item["is_table"]:
            flush()
            table_chunk(item)
            continue
        if item["is_title"] and (split_on_titles or title_context):
            # A title always opens a new section: pending content is flushed
            # and (with title_context) the title rides along as a prefix.
            flush()
            section = item["text"]
            continue
        if buffer and buffer_len + len(item["text"]) > soft_limit:
            flush()
        if not buffer:
            buffer_page = item["page"]
            buffer_type = item["type"]
        if len(item["text"]) > max_chars:
            flush()
            budget = max_chars - (len(section) + 2 if title_context and section else 0)
            window = max(1, min(max_chars, budget))
            for start in range(0, len(item["text"]), max(1, window - overlap)):
                piece = item["text"][start : start + window]
                if start != 0 and len(piece) < min_chars:
                    continue
                prefix = f"{section}\n\n" if title_context and section else ""
                chunks.append(
                    {
                        "text": (prefix + piece)[:MAX_CHUNK_CHARS],
                        "page_number": item["page"],
                        "metadata": {"type": item["type"], "filename": filename},
                    }
                )
            continue
        buffer.append(item["text"])
        buffer_len += len(item["text"])
    flush()
    return chunks


def _chunk_per_element(
    prepared: list[dict[str, Any]], filename: str
) -> list[dict[str, Any]]:
    return [
        {
            "text": item["text"],
            "page_number": item["page"],
            "metadata": {"type": item["type"], "filename": filename},
        }
        for item in prepared
    ]


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
        cache: PipelineCache | None = None,
        parse_profile: str = "best",
        embedding_model: str = "",
        embedding_dim: int = 0,
        chunk_strategy: str = "pack",
        chunk_title_context: bool = True,
        chunk_overlap: int = 0,
    ) -> None:
        self._knowledge = knowledge_service
        self._unstructured = unstructured
        self._embeddings = embeddings
        self._vector = vector_store
        self._max_chars = max_chars
        self._cache = cache
        self._parse_profile = parse_profile
        self._embedding_model = embedding_model
        self._embedding_dim = embedding_dim
        self._chunk_strategy = chunk_strategy
        self._chunk_title_context = chunk_title_context
        self._chunk_overlap = chunk_overlap

    # --- trace ---------------------------------------------------------------

    def _event(
        self,
        doc: Any,
        stage: str,
        status: str,
        detail: dict[str, Any] | None = None,
        duration_ms: int | None = None,
    ) -> None:
        try:
            self._knowledge.add_pipeline_event(
                doc.id,
                doc.kbId,
                stage,
                status,
                detail=json.dumps(detail, ensure_ascii=False) if detail is not None else None,
                duration_ms=duration_ms,
            )
        except Exception:  # tracing must never break ingestion
            logger.exception("failed to record pipeline event (%s/%s)", doc.id, stage)

    # --- pipeline --------------------------------------------------------------

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
        stage = "parse"
        try:
            started = time.perf_counter()
            elements: list[dict] | None = None
            parse_source = "api"
            if self._cache is not None:
                elements = self._cache.load_parse(doc.sha256, self._parse_profile)
                if elements is not None:
                    parse_source = "cache"
            if elements is None:
                elements = self._unstructured.parse_pdf(
                    self._knowledge.document_path(doc), doc.filename
                )
                if self._cache is not None:
                    self._cache.save_parse(doc.sha256, self._parse_profile, elements, "api")
            self._event(
                doc,
                "parse",
                "succeeded",
                {"elements": len(elements), "source": parse_source,
                 "profile": self._parse_profile},
                _elapsed(started),
            )

            stage = "chunk"
            started = time.perf_counter()
            chunks = pack_elements(
                elements,
                doc.filename,
                strategy=self._chunk_strategy,
                max_chars=self._max_chars,
                title_context=self._chunk_title_context,
                overlap=self._chunk_overlap,
            )
            self._event(
                doc,
                "chunk",
                "succeeded",
                {"chunks": len(chunks), "strategy": self._chunk_strategy},
                _elapsed(started),
            )
            if not chunks:
                raise IngestionError("no extractable text (scanned PDF? try profile=best)")

            stage = "embed"
            started = time.perf_counter()
            texts = [chunk["text"] for chunk in chunks]
            vectors: list[list[float]] | None = None
            embed_source = "api"
            if self._cache is not None:
                vectors = self._cache.load_embeddings(
                    texts, model=self._embedding_model, dim=self._embedding_dim
                )
                if vectors is not None:
                    embed_source = "cache"
            if vectors is None:
                vectors = self._embeddings.embed_texts(texts)
                if self._cache is not None:
                    self._cache.save_embeddings(
                        texts, vectors,
                        model=self._embedding_model, dim=self._embedding_dim,
                    )
            self._event(
                doc,
                "embed",
                "succeeded",
                {"vectors": len(vectors), "dim": len(vectors[0]), "source": embed_source},
                _elapsed(started),
            )

            stage = "index"
            started = time.perf_counter()
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
            self._event(doc, "index", "succeeded", {"rows": len(rows)}, _elapsed(started))

            self._knowledge.update_document_status(doc_id, "ready", chunk_count=len(rows))
            logger.info(
                "ingested document=%s chunks=%d collection=%s", doc.id, len(rows), kb.collectionName
            )
        except Exception as exc:
            logger.exception("ingestion failed for document=%s", doc_id)
            self._event(doc, stage, "failed", {"error": f"{type(exc).__name__}: {exc}"})
            self._knowledge.update_document_status(
                doc_id, "failed", error=f"{type(exc).__name__}: {exc}"
            )


def _elapsed(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
