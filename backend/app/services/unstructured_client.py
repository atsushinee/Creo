"""HTTP client for the self-hosted Unstructured partition endpoint (ADR-0004).

Only the multipart call we need — deliberately not the `unstructured` Python
package (dependency discipline). Parameters must be verified against the
running instance's /general/openapi.json (AGENTS.md §12) when upgrading.
"""

import json
from pathlib import Path

import httpx

from app.core.logging import get_logger

logger = get_logger("services.unstructured")


class UnstructuredError(RuntimeError):
    """The partition endpoint call failed."""


class UnstructuredClient:
    """Synchronous client; call from a worker thread (ingestion pipeline)."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str = "",
        timeout: float = 600.0,
        strategy: str = "hi_res",
        languages: list[str] | None = None,
        max_characters: int = 1500,
        new_after_n_chars: int | None = None,
        combine_under: int = 300,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        headers = {"accept": "application/json"}
        if api_key:
            headers["unstructured-api-key"] = api_key
        self._strategy = strategy
        self._languages = list(languages or [])
        self._max_characters = max_characters
        self._new_after_n_chars = new_after_n_chars or int(max_characters * 0.8)
        self._combine_under = combine_under
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers=headers,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def partition_pdf(self, path: Path, filename: str) -> list[dict]:
        """Parse and chunk one PDF; returns raw Unstructured element dicts."""
        # by_title chunking: new_after_n_chars is the soft limit that starts a
        # new chunk, max_characters the hard split (validation: soft <= hard).
        # Repeated multipart fields (languages) are expressed as list values —
        # verified against httpx 0.28.1 (list-of-tuples in `data` is not).
        data: dict[str, str | list[str]] = {
            "strategy": self._strategy,
            "chunking_strategy": "by_title",
            "max_characters": str(self._max_characters),
            "new_after_n_chars": str(self._new_after_n_chars),
            "combine_text_under_n_chars": str(self._combine_under),
            "include_orig_elements": "false",
            "pdf_infer_table_structure": "true",
        }
        if self._languages:
            data["languages"] = self._languages

        with path.open("rb") as pdf:
            files = {"files": (filename, pdf, "application/pdf")}
            try:
                response = self._client.post("/general/v0/general", data=data, files=files)
            except httpx.HTTPError as exc:
                raise UnstructuredError(f"unstructured request failed: {exc}") from exc
        if response.status_code != 200:
            raise UnstructuredError(
                f"unstructured returned {response.status_code}: {response.text[:300]}"
            )
        try:
            elements = response.json()
        except json.JSONDecodeError as exc:
            raise UnstructuredError("unstructured returned invalid JSON") from exc
        if not isinstance(elements, list):
            raise UnstructuredError("unexpected unstructured response shape")
        logger.info("partitioned %s: %d elements", filename, len(elements))
        return elements
