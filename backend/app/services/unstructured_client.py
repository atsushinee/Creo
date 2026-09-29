"""Unstructured Transform API adapter (ADR-0004, updated 2026-09-29).

Wraps the official `unstructured-transform-client` SDK (Transform API v2,
transform.unstructured.io). `parse.run` blocks until the job completes and the
ParseResult always carries the canonical `elements` (SDK 0.18.21; see
TECHNICAL-NOTES) — the adapter flattens them to plain dicts so the ingestion
pipeline stays SDK-agnostic.
"""

from pathlib import Path
from typing import Any

from unstructured_transform_client import TransformClient

from app.core.logging import get_logger

logger = get_logger("services.unstructured")

DEFAULT_SERVER_URL = "https://transform.unstructured.io"


class UnstructuredError(RuntimeError):
    """The Transform API parse call failed."""


def _normalize_server_url(url: str) -> str:
    """The SDK appends /api/v2 paths itself — strip it if a user pasted the
    full API base (e.g. https://transform.unstructured.io/api/v2)."""
    value = url.strip().rstrip("/")
    if value.endswith("/api/v2"):
        value = value[: -len("/api/v2")]
    return value or DEFAULT_SERVER_URL


class UnstructuredClient:
    """Synchronous client; call from a worker thread (ingestion pipeline)."""

    def __init__(
        self,
        api_key: str,
        *,
        server_url: str = DEFAULT_SERVER_URL,
        profile: str = "best",
        timeout_seconds: float | None = None,
        transform_client: Any = None,
    ) -> None:
        self._profile = profile
        self._server_url = _normalize_server_url(server_url)
        # Injectable for tests; the real client needs an API key (constructor
        # raises without one) and is built during KB wiring, never at import.
        self._client = transform_client or TransformClient(
            api_key=api_key,
            server_url=self._server_url,
            timeout_seconds=timeout_seconds,
        )

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            close()

    def parse_pdf(self, path: Path, filename: str) -> list[dict]:
        """Parse one PDF into element dicts for the ingestion pipeline.

        `include=["text_as_html"]` requests the table HTML projection;
        `page_number` (one-based) is returned by default on element metadata.
        """
        try:
            with path.open("rb") as pdf:
                result = self._client.parse.run(
                    input=pdf, include=["text_as_html"], profile=self._profile
                )
        except Exception as exc:
            raise UnstructuredError(f"unstructured parse failed: {exc}") from exc
        elements = [self._element_to_dict(element) for element in (result.elements or [])]
        logger.info("parsed %s: %d elements (profile=%s)", filename, len(elements), self._profile)
        return elements

    @staticmethod
    def _element_to_dict(element: Any) -> dict[str, Any]:
        metadata = getattr(element, "metadata", None)
        return {
            "type": getattr(element, "type", "") or "",
            "text": getattr(element, "text", None),
            "metadata": {
                "page_number": getattr(metadata, "page_number", None),
                "text_as_html": getattr(metadata, "text_as_html", None),
            },
        }
