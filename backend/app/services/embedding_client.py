"""OpenAI-compatible /embeddings client (ADR-0004).

Used for the dense channel (bge-m3 by default); the sparse BM25 channel is
computed server-side by Milvus and needs no client. httpx only — no SDK.
"""

import time
from typing import Any

import httpx

from app.core.logging import get_logger

logger = get_logger("services.embeddings")


class EmbeddingError(RuntimeError):
    """The embeddings endpoint failed (after retries)."""


class OpenAIEmbeddingClient:
    """Synchronous client; call from a worker thread (ingestion pipeline)."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str = "",
        model: str = "BAAI/bge-m3",
        batch_size: int = 16,
        timeout: float = 120.0,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._model = model
        self._batch_size = max(1, batch_size)
        self._max_retries = max(1, max_retries)
        self._retry_backoff = retry_backoff
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers=headers,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed texts in batches; input order is preserved."""
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            vectors.extend(self._embed_batch(texts[start : start + self._batch_size]))
        return vectors

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        payload = {"model": self._model, "input": batch}
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                response = self._client.post("/embeddings", json=payload)
                if response.status_code == 200:
                    data: list[dict[str, Any]] = response.json().get("data", [])
                    ordered = sorted(data, key=lambda item: item.get("index", 0))
                    return [item["embedding"] for item in ordered]
                last_error = EmbeddingError(
                    f"embeddings returned {response.status_code}: {response.text[:200]}"
                )
                if response.status_code < 500 and response.status_code != 429:
                    raise last_error  # auth/validation errors are not retryable
            except httpx.HTTPError as exc:
                last_error = exc
            wait = min(self._retry_backoff * (2**attempt), 8.0)
            logger.warning(
                "embeddings attempt %d/%d failed (%s); retrying in %.1fs",
                attempt + 1,
                self._max_retries,
                last_error,
                wait,
            )
            time.sleep(wait)
        raise last_error or EmbeddingError("embeddings failed")
