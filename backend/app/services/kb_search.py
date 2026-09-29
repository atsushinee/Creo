"""Hybrid retrieval orchestration (ADR-0004): embed the query once, run a
Milvus hybrid search (dense + server-side BM25 sparse) per knowledge base,
then fuse across KBs with Reciprocal Rank Fusion.
"""

from typing import Any, Protocol

from app.core.logging import get_logger

logger = get_logger("services.kb_search")

RRF_K = 60


class KbNotFoundError(RuntimeError):
    """The requested knowledge base does not exist."""


class QueryEmbeddingLike(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class VectorSearchLike(Protocol):
    def has_collection(self, name: str) -> bool: ...
    def hybrid_search(
        self, name: str, query_text: str, query_vector: list[float], *, top_k: int = 5
    ) -> list[dict[str, Any]]: ...


class KnowledgeLookupLike(Protocol):
    def list_kbs(self) -> list[Any]: ...
    def get_kb(self, kb_id: str) -> Any | None: ...


def rrf_merge(result_lists: list[list[dict[str, Any]]], *, limit: int = 5) -> list[dict[str, Any]]:
    """Reciprocal Rank Fusion over per-KB hit lists (keyed by KB + chunk)."""
    scores: dict[tuple[str, str, int], float] = {}
    best: dict[tuple[str, str, int], dict[str, Any]] = {}
    for results in result_lists:
        for rank, hit in enumerate(results):
            key = (
                str(hit.get("kbId", "")),
                str(hit.get("docId", "")),
                int(hit.get("chunkIndex", 0)),
            )
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
            best.setdefault(key, hit)
    merged = sorted(best.items(), key=lambda item: scores[item[0]], reverse=True)[:limit]
    return [{**hit, "score": round(scores[key], 6)} for key, hit in merged]


class KbSearchService:
    """Query-side facade used by the agent tool (no FastAPI/agent imports)."""

    def __init__(
        self,
        knowledge_service: KnowledgeLookupLike,
        embeddings: QueryEmbeddingLike,
        vector_store: VectorSearchLike,
    ) -> None:
        self._knowledge = knowledge_service
        self._embeddings = embeddings
        self._vector = vector_store

    def search(
        self, query: str, *, kb_id: str | None = None, top_k: int = 5
    ) -> list[dict[str, Any]]:
        query = query.strip()
        if not query:
            return []
        if kb_id is not None:
            kb = self._knowledge.get_kb(kb_id)
            if kb is None:
                raise KbNotFoundError(f"knowledge base not found: {kb_id}")
            targets = [kb]
        else:
            targets = self._knowledge.list_kbs()
        if not targets:
            return []

        vector = self._embeddings.embed_texts([query])[0]
        result_lists: list[list[dict[str, Any]]] = []
        for kb in targets:
            if not self._vector.has_collection(kb.collectionName):
                continue  # KB created but nothing ingested yet
            hits = self._vector.hybrid_search(kb.collectionName, query, vector, top_k=top_k)
            for hit in hits:
                hit["kbId"] = kb.id
                hit["kbName"] = kb.name
            result_lists.append(hits)
        return rrf_merge(result_lists, limit=top_k)
