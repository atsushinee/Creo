"""Milvus vector-store boundary — the ONLY module allowed to import pymilvus
(AGENTS.md §2, enforced by scripts/check-boundaries.mjs). See ADR-0004.

One collection per knowledge base. The sparse channel is computed SERVER-SIDE
by a BM25 function over the `text` field: rows are inserted without the sparse
field, and sparse queries pass raw query text. API shapes verified against
pymilvus 3.0.2 (TECHNICAL-NOTES).
"""

import json
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
    ) -> None:
        self._dim = dim
        self._analyzer_params = analyzer_params(analyzer)
        # Fails fast on unreachable/misconfigured endpoints; the caller (main
        # lifespan) treats that as "KB disabled" and logs a warning.
        self._client = MilvusClient(uri=uri, token=token or None)

    def close(self) -> None:
        self._client.close()

    @property
    def analyzer_params(self) -> dict[str, Any]:
        return dict(self._analyzer_params)

    def has_collection(self, name: str) -> bool:
        return bool(self._client.has_collection(name))

    def ensure_collection(self, name: str) -> None:
        if self.has_collection(name):
            return
        schema = self._client.create_schema(auto_id=True, enable_dynamic_field=False)
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
        index_params = self._client.prepare_index_params()
        index_params.add_index(field_name="dense", index_type="AUTOINDEX", metric_type="COSINE")
        # AUTOINDEX must not be used for the BM25 sparse field.
        index_params.add_index(
            field_name="sparse", index_type="SPARSE_INVERTED_INDEX", metric_type="BM25"
        )
        self._client.create_collection(name, schema=schema, index_params=index_params)
        logger.info(
            "created milvus collection %s (dim=%d, analyzer=%s)",
            name,
            self._dim,
            self._analyzer_params,
        )

    def insert_chunks(self, name: str, rows: list[dict[str, Any]]) -> int:
        """Insert chunk rows: text/dense/doc_id/chunk_index/page_number/metadata."""
        self._client.insert(collection_name=name, data=rows)
        return len(rows)

    def delete_doc(self, name: str, doc_id: str) -> None:
        if not self.has_collection(name):
            return
        self._client.delete(collection_name=name, filter=f'doc_id == "{doc_id}"')

    def drop_collection(self, name: str) -> None:
        if not self.has_collection(name):
            return
        self._client.drop_collection(name)
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
        results = self._client.hybrid_search(
            collection_name=name,
            reqs=requests,
            ranker=RRFRanker(RRF_K),
            limit=top_k,
            output_fields=["text", "doc_id", "chunk_index", "page_number", "metadata"],
        )
        return [normalize_hit(hit) for hit in (results[0] if results else [])]
