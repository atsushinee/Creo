"""One-off smoke test: run the KB pipeline against the real services.

Usage (from backend/):  uv run python scripts/smoke_kb.py [path/to/file.pdf]

Stages: Unstructured parse → client-side chunking → embeddings → Zilliz insert
+ hybrid search + delete → collection cleanup (temporary kb_smoke_* collection,
dropped even on failure; not part of pytest).

Paid stages are cached on disk under data/smoke/ so a late-stage failure never
re-spends API quota on a rerun:
  - parse:      data/smoke/parse/{pdf_sha}-{profile}.json      (element dicts)
  - embeddings: data/smoke/embed/{texts_sha}-{model}-{dim}.json (vectors)
Cache keys embed the PDF hash, profile, chunk-texts hash, model and dim, so
changing any input invalidates the stale cache automatically. Console output
is tee'd to data/smoke/run.log for post-mortems.
"""

import hashlib
import json
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ root

from app.core.config import get_settings  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402
from app.services.embedding_client import OpenAIEmbeddingClient  # noqa: E402
from app.services.ingestion_service import pack_elements  # noqa: E402
from app.services.kb_vector_store import MilvusVectorStore  # noqa: E402
from app.services.unstructured_client import UnstructuredClient  # noqa: E402

DEFAULT_PDF = Path(r"C:\Users\freedom\Desktop\yushu.pdf")


def preview(text: str, limit: int = 90) -> str:
    return " ".join(text.split())[:limit]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


class Cache:
    """JSON artifacts under data/smoke/, keyed by content fingerprints."""

    def __init__(self, root: Path, log_path: Path) -> None:
        self.parse_dir = root / "parse"
        self.embed_dir = root / "embed"
        self.log_path = log_path
        self.parse_dir.mkdir(parents=True, exist_ok=True)
        self.embed_dir.mkdir(parents=True, exist_ok=True)

    def load(self, path: Path) -> object | None:
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
        return None

    def save(self, path: Path, payload: object) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    settings = get_settings()
    setup_logging(settings.log_level)

    pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PDF
    if not pdf.is_file():
        print(f"✗ PDF not found: {pdf}")
        return 1

    cache_root = settings.kb_data_dir.parent / "smoke"
    log_path = cache_root / "run.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cache = Cache(cache_root, log_path)

    class Tee:
        def __init__(self, *streams: object) -> None:
            self._streams = streams

        def write(self, text: str) -> int:
            for stream in self._streams:
                stream.write(text)
            return len(text)

        def flush(self) -> None:
            for stream in self._streams:
                stream.flush()

    log_file = log_path.open("a", encoding="utf-8")
    log_file.write(f"\n===== run {datetime.now(UTC).isoformat()} =====\n")
    sys.stdout = Tee(sys.__stdout__, log_file)  # type: ignore[assignment]

    print(f"PDF: {pdf} ({pdf.stat().st_size // 1024} KB)")
    configured = {
        "milvus": bool(settings.milvus_uri),
        "unstructured": bool(settings.unstructured_api_key),
        "embeddings": bool(settings.kb_embedding_base_url and settings.kb_embedding_api_key),
    }
    print(
        f"config: {configured}  profile={settings.unstructured_profile}  "
        f"dim={settings.kb_embedding_dim}  analyzer={settings.kb_analyzer}"
    )
    print(f"cache: {cache_root}")
    if not all(configured.values()):
        print("✗ incomplete KB config (see above)")
        return 1

    pdf_sha = sha256_bytes(pdf.read_bytes())

    # --- 1. Unstructured Transform API (cached) ------------------------------
    parse_cache = cache.parse_dir / f"{pdf_sha[:16]}-{settings.unstructured_profile}.json"
    cached = cache.load(parse_cache)
    if isinstance(cached, dict) and isinstance(cached.get("elements"), list):
        elements = cached["elements"]
        print(f"\n[1] parse: CACHE HIT ({parse_cache.name}) → {len(elements)} elements")
    else:
        print("\n[1] parsing via Unstructured Transform API (no cache) ...")
        parser = UnstructuredClient(
            settings.unstructured_api_key,
            server_url=settings.unstructured_server_url,
            profile=settings.unstructured_profile,
            timeout_seconds=settings.unstructured_timeout_seconds,
        )
        started = time.perf_counter()
        try:
            elements = parser.parse_pdf(pdf, pdf.name)
        except Exception as exc:
            print(f"✗ parse failed after {time.perf_counter() - started:.1f}s: {exc}")
            return 1
        cache.save(parse_cache, {
            "pdf": str(pdf),
            "pdf_sha256": pdf_sha,
            "profile": settings.unstructured_profile,
            "elements": elements,
        })
        print(f"    OK: {len(elements)} elements in {time.perf_counter() - started:.1f}s (cached)")
    print(f"    types: {dict(Counter(e['type'] for e in elements))}")
    pages = sorted({e["metadata"]["page_number"] for e in elements if e["metadata"]["page_number"]})
    print(f"    pages: {pages[0]}..{pages[-1]}" if pages else "    pages: none reported")
    if elements:
        print(f"    first: {preview(elements[0]['text'] or '')!r}")

    # --- 2. client-side chunking (pure, free) ---------------------------------
    chunks = pack_elements(elements, pdf.name, max_chars=settings.kb_chunk_max_characters)
    print(f"\n[2] chunks: {len(chunks)}")
    if not chunks:
        print("✗ no chunks produced")
        return 1
    lengths = [len(c["text"]) for c in chunks]
    print(f"    len min/avg/max: {min(lengths)}/{sum(lengths) // len(lengths)}/{max(lengths)}")
    print(f"    chunk[0] p.{chunks[0]['page_number']}: {preview(chunks[0]['text'])!r}")

    # --- 3. embeddings (cached by chunk texts + model + dim) ------------------
    texts_sig = sha256_text("\n<chunk>\n".join(c["text"] for c in chunks))
    model_tag = settings.kb_embedding_model.replace("/", "_")
    embed_cache = cache.embed_dir / f"{texts_sig}-{model_tag}-{settings.kb_embedding_dim}.json"
    cached = cache.load(embed_cache)
    vectors = None
    if isinstance(cached, dict) and isinstance(cached.get("vectors"), list):
        candidates = cached["vectors"]
        if len(candidates) == len(chunks):
            vectors = candidates
            print(f"\n[3] embeddings: CACHE HIT ({embed_cache.name}) → {len(vectors)} vectors")
    if vectors is None:
        print("\n[3] embedding via OpenAI-compatible endpoint (no cache) ...")
        embedder = OpenAIEmbeddingClient(
            settings.kb_embedding_base_url,
            api_key=settings.kb_embedding_api_key,
            model=settings.kb_embedding_model,
        )
        started = time.perf_counter()
        try:
            vectors = embedder.embed_texts([c["text"] for c in chunks])
        except Exception as exc:
            print(f"✗ embedding failed after {time.perf_counter() - started:.1f}s: {exc}")
            return 1
        cache.save(
            embed_cache,
            {
                "model": settings.kb_embedding_model,
                "dim": settings.kb_embedding_dim,
                "texts_sha": texts_sig,
                "vectors": vectors,
            },
        )
        print(f"    OK: {len(vectors)} vectors in {time.perf_counter() - started:.1f}s (cached)")
    print(f"    dim={len(vectors[0])} (expected {settings.kb_embedding_dim})")
    if len(vectors[0]) != settings.kb_embedding_dim:
        print("✗ dimension mismatch with CREO_KB_EMBEDDING_DIM")
        return 1

    # --- 4. Milvus / Zilliz insert + hybrid search + delete (always live) -----
    collection = f"kb_smoke_{uuid4().hex[:8]}"
    store = MilvusVectorStore(
        settings.milvus_uri,
        token=settings.milvus_token,
        dim=settings.kb_embedding_dim,
        analyzer=settings.kb_analyzer,
        timeout=60.0,
    )

    def drop_best_effort(name: str, *, tries: int = 3) -> bool:
        # Serverless DDL occasionally answers DEADLINE_EXCEEDED under load;
        # cleanup must never mask the test result, so retry and report.
        for attempt in range(1, tries + 1):
            try:
                store.drop_collection(name)
                return True
            except Exception as exc:
                print(f"    ⚠ drop {name} attempt {attempt}/{tries} failed: {exc}")
                time.sleep(2)
        return False

    print(f"\n[4] Milvus: creating temporary collection {collection} ...")
    try:
        leftovers = [n for n in store.list_collections() if n.startswith("kb_smoke_")]
        for leftover in leftovers:
            print(f"    sweeping leftover {leftover} from an earlier run")
            drop_best_effort(leftover)
        started = time.perf_counter()
        store.ensure_collection(collection)
        print(
            f"    collection ready in {time.perf_counter() - started:.1f}s "
            f"(sparse index auto: zilliz={'zilliz' in settings.milvus_uri.lower()})"
        )

        started = time.perf_counter()
        rows = [
            {
                "text": chunk["text"],
                "dense": vector,
                "doc_id": "smoke-test",
                "chunk_index": index,
                "page_number": chunk["page_number"],
                "metadata": chunk["metadata"],
            }
            for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
        ]
        store.insert_chunks(collection, rows)
        print(f"    inserted {len(rows)} rows in {time.perf_counter() - started:.1f}s")

        for label, query in (
            ("keyword-ish", preview(chunks[0]["text"], 14)),
            ("semantic", "这份文档主要讲了什么内容"),
        ):
            started = time.perf_counter()
            hits = store.hybrid_search(collection, query, vectors[0], top_k=3)
            elapsed = (time.perf_counter() - started) * 1000
            print(f"    search [{label} {query!r}] → {len(hits)} hits in {elapsed:.0f} ms")
            for rank, hit in enumerate(hits, start=1):
                print(
                    f"      #{rank} score={hit['score']:.4f} p.{hit['page']} "
                    f"{preview(hit['text'], 60)!r}"
                )

        store.delete_doc(collection, "smoke-test")
        remaining = store.hybrid_search(
            collection, preview(chunks[0]["text"], 14), vectors[0], top_k=3
        )
        print(f"    after delete_doc: {len(remaining)} hits (expect 0)")
    finally:
        if drop_best_effort(collection):
            print(f"    dropped {collection}")
        else:
            print(f"    ⚠ could not drop {collection} — remove it in the Zilliz console")
        store.close()

    print("\n✓ smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
