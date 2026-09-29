"""Content-addressed caches for paid pipeline stages (ADR-0004 update).

Re-running a failed ingest, re-ingesting an identical file, or ingesting the
same document into another knowledge base must not re-spend API quota. The
cache lives under `{kb_data_dir}/_cache` and is keyed by content fingerprints:

  parse/{pdf_sha256[:16]}-{profile}.json            → element dicts
  embed/{sha256(chunk texts)[:24]}-{model}-{dim}.json → dense vectors

Chunk texts carry no filename, so the same content ingested under a different
name still hits the embedding cache.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger("services.pipeline_cache")


def _texts_fingerprint(texts: list[str]) -> str:
    joined = "\n<chunk>\n".join(texts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:24]


class PipelineCache:
    """Best-effort JSON cache; any read problem is treated as a miss."""

    def __init__(self, root: Path) -> None:
        self._parse_dir = root / "parse"
        self._embed_dir = root / "embed"
        self._parse_dir.mkdir(parents=True, exist_ok=True)
        self._embed_dir.mkdir(parents=True, exist_ok=True)

    def _load(self, path: Path) -> dict[str, Any] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _save(self, path: Path, payload: dict[str, Any]) -> None:
        try:
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:  # cache must never break the pipeline
            logger.warning("pipeline cache write failed (%s): %s", path.name, exc)

    # --- parse ---------------------------------------------------------------

    def load_parse(self, pdf_sha256: str, profile: str) -> list[dict] | None:
        payload = self._load(self._parse_dir / f"{pdf_sha256[:16]}-{profile}.json")
        elements = payload.get("elements") if payload else None
        return elements if isinstance(elements, list) else None

    def save_parse(
        self, pdf_sha256: str, profile: str, elements: list[dict], source: str
    ) -> None:
        self._save(
            self._parse_dir / f"{pdf_sha256[:16]}-{profile}.json",
            {"pdf_sha256": pdf_sha256, "profile": profile, "source": source, "elements": elements},
        )

    # --- embeddings ------------------------------------------------------------

    def load_embeddings(
        self, texts: list[str], *, model: str, dim: int
    ) -> list[list[float]] | None:
        path = self._embed_dir / f"{_texts_fingerprint(texts)}-{model.replace('/', '_')}-{dim}.json"
        payload = self._load(path)
        if not payload:
            return None
        vectors = payload.get("vectors")
        if isinstance(vectors, list) and len(vectors) == len(texts):
            return vectors
        return None

    def save_embeddings(
        self, texts: list[str], vectors: list[list[float]], *, model: str, dim: int
    ) -> None:
        self._save(
            self._embed_dir / f"{_texts_fingerprint(texts)}-{model.replace('/', '_')}-{dim}.json",
            {"model": model, "dim": dim, "texts": len(texts), "vectors": vectors},
        )
