"""One-off smoke test: run the KB pipeline against the real services.

Usage (from backend/):  uv run python scripts/smoke_kb.py [path/to/file.pdf]

Stages:
  1. Unstructured Transform API parse      (paid — cached)
  2. client-side chunking                  (pure)
  3. embeddings                            (paid — cached)
  4. raw Milvus insert + hybrid search + delete + cleanup
  5. app-level chain: real IngestionService (trace events) + KbSearchService

Paid stages are cached so late failures never re-spend API quota:
  - production pipeline cache:  data/kb/_cache/{parse,embed}/...  (stage 5,
    shared with the real backend — content-addressed by PipelineCache)
  - smoke-only mirrors are NOT used; stages 1/3 read through PipelineCache
    directly, so a smoke run warms the same cache the app uses.
Console output is tee'd to data/smoke/run.log. Temporary kb_smoke_* /
app-smoke collections are dropped even on failure. Not part of pytest.
"""

import hashlib
import shutil
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
from app.services.ingestion_service import IngestionService, pack_elements  # noqa: E402
from app.services.kb_search import KbSearchService  # noqa: E402
from app.services.kb_service import SqliteKnowledgeService  # noqa: E402
from app.services.kb_vector_store import MilvusVectorStore  # noqa: E402
from app.services.pipeline_cache import PipelineCache  # noqa: E402
from app.services.unstructured_client import UnstructuredClient  # noqa: E402

DEFAULT_PDF = Path(r"C:\Users\freedom\Desktop\yushu.pdf")


def preview(text: str, limit: int = 90) -> str:
    return " ".join(text.split())[:limit]


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
    (settings.kb_data_dir / "_cache").mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("a", encoding="utf-8")
    log_file.write(f"\n===== run {datetime.now(UTC).isoformat()} =====\n")

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
    print(f"cache: {settings.kb_data_dir / '_cache'}")
    if not all(configured.values()):
        print("✗ incomplete KB config (see above)")
        return 1

    pdf_sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    pipeline_cache = PipelineCache(settings.kb_data_dir / "_cache")
    parser = UnstructuredClient(
        settings.unstructured_api_key,
        server_url=settings.unstructured_server_url,
        profile=settings.unstructured_profile,
        timeout_seconds=settings.unstructured_timeout_seconds,
    )
    embedder = OpenAIEmbeddingClient(
        settings.kb_embedding_base_url,
        api_key=settings.kb_embedding_api_key,
        model=settings.kb_embedding_model,
    )

    # --- 1. Unstructured Transform API (cached) -------------------------------
    started = time.perf_counter()
    elements = pipeline_cache.load_parse(pdf_sha, settings.unstructured_profile)
    if elements is not None:
        print(f"\n[1] parse: CACHE HIT → {len(elements)} elements")
    else:
        print("\n[1] parsing via Unstructured Transform API (no cache) ...")
        try:
            elements = parser.parse_pdf(pdf, pdf.name)
        except Exception as exc:
            print(f"✗ parse failed after {time.perf_counter() - started:.1f}s: {exc}")
            return 1
        pipeline_cache.save_parse(pdf_sha, settings.unstructured_profile, elements, "api")
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

    # --- 3. embeddings (cached) ------------------------------------------------
    started = time.perf_counter()
    texts = [chunk["text"] for chunk in chunks]
    vectors = pipeline_cache.load_embeddings(
        texts, model=settings.kb_embedding_model, dim=settings.kb_embedding_dim
    )
    if vectors is not None:
        print(f"\n[3] embeddings: CACHE HIT → {len(vectors)} vectors")
    else:
        print("\n[3] embedding via OpenAI-compatible endpoint (no cache) ...")
        try:
            vectors = embedder.embed_texts(texts)
        except Exception as exc:
            print(f"✗ embedding failed after {time.perf_counter() - started:.1f}s: {exc}")
            return 1
        pipeline_cache.save_embeddings(
            texts, vectors, model=settings.kb_embedding_model, dim=settings.kb_embedding_dim
        )
        print(f"    OK: {len(vectors)} vectors in {time.perf_counter() - started:.1f}s (cached)")
    print(f"    dim={len(vectors[0])} (expected {settings.kb_embedding_dim})")
    if len(vectors[0]) != settings.kb_embedding_dim:
        print("✗ dimension mismatch with CREO_KB_EMBEDDING_DIM")
        return 1

    # --- 4. raw Milvus: insert + hybrid search + delete ------------------------
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
        leftovers = [
            n
            for n in store.list_collections()
            if n.startswith("kb_smoke_") or n.startswith("app_smoke_")
        ]
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

    # --- 5. app-level chain: IngestionService + trace + KbSearchService --------
    # Real app wiring (same construction as main.py) against a throwaway KB;
    # stages 1/3 warmed the shared pipeline cache, so this is quota-free.
    print("\n[5] app-level chain (IngestionService + trace + KbSearchService) ...")
    run_dir = cache_root / f"run-{datetime.now(UTC).strftime('%H%M%S')}"
    app_store = MilvusVectorStore(
        settings.milvus_uri,
        token=settings.milvus_token,
        dim=settings.kb_embedding_dim,
        analyzer=settings.kb_analyzer,
        timeout=60.0,
    )
    kb_service: SqliteKnowledgeService | None = None
    collection_name: str | None = None
    try:
        kb_service = SqliteKnowledgeService(run_dir / "kb")
        kb = kb_service.create_kb("app-smoke")
        collection_name = kb.collectionName
        with pdf.open("rb") as stream:
            doc = kb_service.save_upload(
                kb.id, pdf.name, stream, max_bytes=settings.kb_upload_max_bytes
            )
        ingestion = IngestionService(
            kb_service,
            parser,
            embedder,
            app_store,
            max_chars=settings.kb_chunk_max_characters,
            cache=pipeline_cache,
            parse_profile=settings.unstructured_profile,
            embedding_model=settings.kb_embedding_model,
            embedding_dim=settings.kb_embedding_dim,
        )
        started = time.perf_counter()
        ingestion.ingest(doc.id)
        final = kb_service.get_document(doc.id)
        print(
            f"    ingest → status={final.status if final else '?'} "
            f"chunks={final.chunkCount if final else 0} "
            f"in {time.perf_counter() - started:.1f}s"
        )
        for event in kb_service.list_pipeline_events(doc.id):
            print(f"      trace: {event.stage:<7} {event.status:<9} {event.durationMs} ms")

        searcher = KbSearchService(kb_service, embedder, app_store)
        hits = searcher.search("宇树科技 经营宗旨", top_k=3)
        print(f"    search → {len(hits)} hits")
        for rank, hit in enumerate(hits, start=1):
            source = (hit.get("metadata") or {}).get("filename", "?")
            print(
                f"      #{rank} {source} p.{hit.get('page')} {preview(hit.get('text', ''), 50)!r}"
            )
        if final is None or final.status != "ready" or not hits:
            print("✗ app-level chain failed")
            return 1
    finally:
        if collection_name is not None:
            try:
                app_store.drop_collection(collection_name)
                print(f"    dropped {collection_name}")
            except Exception as exc:
                print(f"    ⚠ could not drop {collection_name}: {exc}")
        if kb_service is not None:
            kb_service.close()
        shutil.rmtree(run_dir, ignore_errors=True)
        app_store.close()

    print("\n✓ smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
