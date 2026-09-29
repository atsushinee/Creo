"""Milvus vector-store boundary — the ONLY module allowed to import pymilvus
(AGENTS.md §2, enforced by scripts/check-boundaries.mjs). See ADR-0004.

One collection per knowledge base. The sparse channel is computed SERVER-SIDE
by a BM25 function over the `text` field: rows are inserted without the sparse
field, and sparse queries pass raw query text. API shapes verified against
pymilvus 3.0.2 (TECHNICAL-NOTES).

The Milvus connection is established lazily on first use: startup never dials
the network, so a slow/unreachable cluster cannot take the KB registry down
(it only fails the operations that actually need vectors).
"""

import json
import threading
from typing import Any

from pymilvus import (
    AnnSearchRequest,
    DataType,
    Function,
    FunctionType,
    MilvusClient,
    RRFRanker,
)

from app.core.logging import get_logger

logger = get_logger("services.kb_vector_store")

SPARSE_DROP_RATIO = 0.2
RRF_K = 60


class VectorStoreError(RuntimeError):
    """Milvus vector store failure."""


def analyzer_params(spec: str) -> dict[str, Any]:
    """Map CREO_KB_ANALYZER to Milvus analyzer params.

    'chinese' / 'english' / 'standard' -> {"type": ...}; a JSON object is
    passed through verbatim (e.g. a custom jieba + filter setup).
    """
    value = spec.strip()
    if value.startswith("{"):
        try:
            params = json.loads(value)
        except json.JSONDecodeError as exc:
            raise VectorStoreError(f"invalid analyzer JSON: {spec!r}") from exc
        if not isinstance(params, dict):
            raise VectorStoreError(f"analyzer JSON must be an object: {spec!r}")
        return params
    return {"type": value or "standard"}


def sparse_index_type(uri: str) -> str:
    """Sparse index type for the BM25 field.

    Zilliz Cloud (dedicated and serverless) manages index internals and only
    accepts AUTOINDEX; self-hosted Milvus needs an explicit
    SPARSE_INVERTED_INDEX (AUTOINDEX does not cover BM25 sparse fields there).
    """
    return "AUTOINDEX" if "zilliz" in uri.lower() else "SPARSE_INVERTED_INDEX"


def normalize_hit(hit: Any) -> dict[str, Any]:
    """Flatten one search hit (dict or object form) into a plain payload."""
    entity = hit.get("entity", {}) if isinstance(hit, dict) else getattr(hit, "entity", {}) or {}
    score = hit.get("distance", 0.0) if isinstance(hit, dict) else getattr(hit, "distance", 0.0)
    return {
        "text": str(entity.get("text", "")),
        "docId": str(entity.get("doc_id", "")),
        "chunkIndex": int(entity.get("chunk_index") or 0),
        "page": int(entity.get("page_number") or 0),
        "metadata": entity.get("metadata") or {},
        "score": float(score or 0.0),
    }


class MilvusVectorStore:
    """Thin wrapper over MilvusClient for the KB schema and hybrid search."""

    def __init__(
        self,
        uri: str,
        *,
        token: str = "",
        dim: int = 1024,
        analyzer: str = "chinese",
        timeout: float = 60.0,
        client: MilvusClient | None = None,
    ) -> None:
        self._dim = dim
        self._uri = uri
        self._token = token
        self._timeout = timeout
        self._analyzer_params = analyzer_params(analyzer)
        self._client_lock = threading.Lock()
        self._client = client  # injectable for tests; lazily connected otherwise

    @property
    def client(self) -> MilvusClient:
        """Connect on first use — startup must not dial the network."""
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    self._client = MilvusClient(uri=self._uri, token=self._token or None)
        return self._client

    def close(self) -> None:
        self._client = None

    @property
    def analyzer_params(self) -> dict[str, Any]:
        return dict(self._analyzer_params)

    def list_collections(self) -> list[str]:
        return list(self.client.list_collections())

    def has_collection(self, name: str) -> bool:
        return bool(self.client.has_collection(name))

    def ensure_collection(self, name: str) -> None:
        if self.has_collection(name):
            return
        schema = self.client.create_schema(auto_id=True, enable_dynamic_field=False)
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field(
            "text",
            DataType.VARCHAR,
            max_length=65_535,
            enable_analyzer=True,
            analyzer_params=self._analyzer_params,
        )
        schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)
        schema.add_field("dense", DataType.FLOAT_VECTOR, dim=self._dim)
        schema.add_field("doc_id", DataType.VARCHAR, max_length=64)
        schema.add_field("chunk_index", DataType.INT16)
        schema.add_field("page_number", DataType.INT16)
        schema.add_field("metadata", DataType.JSON)
        schema.add_function(
            Function(
                name="text_bm25",
                function_type=FunctionType.BM25,
                input_field_names=["text"],
                output_field_names=["sparse"],
            )
        )
        index_params = self.client.prepare_index_params()
        index_params.add_index(field_name="dense", index_type="AUTOINDEX", metric_type="COSINE")
        index_params.add_index(
            field_name="sparse",
            index_type=sparse_index_type(self._uri),
            metric_type="BM25",
        )
        self.client.create_collection(
            name, schema=schema, index_params=index_params, timeout=self._timeout
        )
        logger.info(
            "created milvus collection %s (dim=%d, analyzer=%s)",
            name,
            self._dim,
            self._analyzer_params,
        )

    def insert_chunks(self, name: str, rows: list[dict[str, Any]]) -> int:
        """Insert chunk rows: text/dense/doc_id/chunk_index/page_number/metadata."""
        self.client.insert(collection_name=name, data=rows, timeout=self._timeout)
        return len(rows)

    def delete_doc(self, name: str, doc_id: str) -> None:
        if not self.has_collection(name):
            return
        self.client.delete(
            collection_name=name, filter=f'doc_id == "{doc_id}"', timeout=self._timeout
        )

    def drop_collection(self, name: str) -> None:
        if not self.has_collection(name):
            return
        self.client.drop_collection(name, timeout=self._timeout)
        logger.info("dropped milvus collection %s", name)

    def hybrid_search(
        self,
        name: str,
        query_text: str,
        query_vector: list[float],
        *,
        top_k: int = 5,
        filter_expr: str = "",
    ) -> list[dict[str, Any]]:
        """Dense (COSINE) + sparse (server-side BM25 over raw query text) fusion."""
        requests = [
            AnnSearchRequest(
                data=[query_text],
                anns_field="sparse",
                param={
                    "metric_type": "BM25",
                    "params": {"drop_ratio_search": SPARSE_DROP_RATIO},
                },
                limit=top_k,
                expr=filter_expr or None,
            ),
            AnnSearchRequest(
                data=[query_vector],
                anns_field="dense",
                param={"metric_type": "COSINE"},
                limit=top_k,
                expr=filter_expr or None,
            ),
        ]
        results = self.client.hybrid_search(
            collection_name=name,
            reqs=requests,
            ranker=RRFRanker(RRF_K),
            limit=top_k,
            output_fields=["text", "doc_id", "chunk_index", "page_number", "metadata"],
            timeout=self._timeout,
        )
        return [normalize_hit(hit) for hit in (results[0] if results else [])]

    def search_dense(
        self, name: str, query_vector: list[float], *, top_k: int = 5, filter_expr: str = ""
    ) -> list[dict[str, Any]]:
        """Single-channel dense search (retrieval testing / debugging)."""
        results = self.client.search(
            collection_name=name,
            data=[query_vector],
            anns_field="dense",
            limit=top_k,
            filter=filter_expr,
            output_fields=["text", "doc_id", "chunk_index", "page_number", "metadata"],
            timeout=self._timeout,
        )
        return [normalize_hit(hit) for hit in (results[0] if results else [])]

    def query_chunks(self, name: str, doc_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
        """All indexed chunks of one document (parse-result viewer)."""
        if not self.has_collection(name):
            return []
        rows = self.client.query(
            collection_name=name,
            filter=f'doc_id == "{doc_id}"',
            output_fields=["text", "chunk_index", "page_number"],
            limit=limit,
            timeout=self._timeout,
        )
        return [
            {
                "text": str(row.get("text", "")),
                "chunkIndex": int(row.get("chunk_index") or 0),
                "page": int(row.get("page_number") or 0),
            }
            for row in rows
        ]

    def search_sparse(
        self, name: str, query_text: str, *, top_k: int = 5, filter_expr: str = ""
    ) -> list[dict[str, Any]]:
        """Single-channel BM25 search over raw query text (retrieval testing)."""
        results = self.client.search(
            collection_name=name,
            data=[query_text],
            anns_field="sparse",
            limit=top_k,
            filter=filter_expr,
            search_params={
                "metric_type": "BM25",
                "params": {"drop_ratio_search": SPARSE_DROP_RATIO},
            },
            output_fields=["text", "doc_id", "chunk_index", "page_number", "metadata"],
            timeout=self._timeout,
        )
        return [normalize_hit(hit) for hit in (results[0] if results else [])]
