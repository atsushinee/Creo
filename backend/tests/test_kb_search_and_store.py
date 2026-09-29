"""Pure helpers of the Milvus boundary + cross-KB RRF fusion (no server needed)."""

import pytest

from app.services.kb_search import KbNotFoundError, KbSearchService, rrf_merge
from app.services.kb_vector_store import (
    VectorStoreError,
    analyzer_params,
    normalize_hit,
    sparse_index_type,
)


def test_sparse_index_type_by_uri() -> None:
    assert (
        sparse_index_type("https://in03-abc.serverless.gcp-us-west1.cloud.zilliz.com")
        == "AUTOINDEX"
    )
    assert sparse_index_type("https://in03-abc.api-us-west-1.zillizcloud.com") == "AUTOINDEX"
    assert sparse_index_type("http://localhost:19530") == "SPARSE_INVERTED_INDEX"


def test_analyzer_params_named_types() -> None:
    assert analyzer_params("chinese") == {"type": "chinese"}
    assert analyzer_params("english") == {"type": "english"}
    assert analyzer_params("") == {"type": "standard"}


def test_analyzer_params_json_passthrough() -> None:
    assert analyzer_params('{"tokenizer": "jieba"}') == {"tokenizer": "jieba"}


def test_analyzer_params_invalid_json() -> None:
    with pytest.raises(VectorStoreError):
        analyzer_params("{bad")


def test_normalize_hit_dict_and_object() -> None:
    mapping = normalize_hit(
        {
            "distance": 0.5,
            "entity": {
                "text": "t",
                "doc_id": "d1",
                "chunk_index": 1,
                "page_number": 2,
                "metadata": {"filename": "f.pdf"},
            },
        }
    )
    assert mapping["text"] == "t"
    assert mapping["docId"] == "d1"
    assert mapping["chunkIndex"] == 1
    assert mapping["page"] == 2
    assert mapping["metadata"] == {"filename": "f.pdf"}
    assert mapping["score"] == 0.5

    class ObjectHit:
        distance = 0.25
        entity = {"text": "x", "doc_id": "d2", "chunk_index": None, "page_number": None}

    obj = normalize_hit(ObjectHit())
    assert obj["score"] == 0.25
    assert obj["chunkIndex"] == 0
    assert obj["page"] == 0
    assert obj["metadata"] == {}


def hit(kb_id: str, doc_id: str, chunk: int) -> dict:
    return {"kbId": kb_id, "docId": doc_id, "chunkIndex": chunk, "text": f"{doc_id}:{chunk}"}


def test_rrf_merge_interleaves_and_respects_limit() -> None:
    merged = rrf_merge(
        [[hit("a", "d1", 0), hit("a", "d3", 0)], [hit("b", "d2", 0), hit("b", "d4", 0)]],
        limit=3,
    )
    assert len(merged) == 3
    assert merged[0]["score"] >= merged[1]["score"] >= merged[2]["score"]
    assert {m["kbId"] for m in merged} == {"a", "b"}


def test_rrf_merge_fuses_same_key() -> None:
    first = [hit("a", "d1", 0), hit("a", "d3", 0)]
    second = [hit("b", "d2", 0), hit("a", "d1", 0)]  # d1 appears in both lists
    merged = rrf_merge([first, second], limit=10)
    assert len(merged) == 3  # duplicate key collapsed
    consensus = next(m for m in merged if m["docId"] == "d1")
    assert consensus["score"] > 1.0 / 61  # accumulated from both lists


class FakeKbService:
    def __init__(self, kbs: list):
        self._kbs = kbs

    def list_kbs(self) -> list:
        return list(self._kbs)

    def get_kb(self, kb_id: str):
        return next((kb for kb in self._kbs if kb.id == kb_id), None)


class FakeEmbeddings:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 2.0] for _ in texts]


class FakeVector:
    def __init__(self, existing: set[str], results: dict[str, list[dict]]):
        self._existing = existing
        self._results = results
        self.calls: list[dict] = []

    def has_collection(self, name: str) -> bool:
        return name in self._existing

    def hybrid_search(
        self,
        name: str,
        query_text: str,
        query_vector: list,
        *,
        top_k: int = 5,
        filter_expr: str = "",
    ):
        self.calls.append({"collection": name, "filter": filter_expr})
        return self._results.get(name, [])

    def search_dense(self, name: str, query_vector: list, *, top_k: int = 5, filter_expr: str = ""):
        return self._results.get(name, [])

    def search_sparse(self, name: str, query_text: str, *, top_k: int = 5, filter_expr: str = ""):
        return self._results.get(name, [])


def make_search_service(kbs, existing, results):
    return KbSearchService(FakeKbService(kbs), FakeEmbeddings(), FakeVector(existing, results))


def make_kb(kb_id: str, collection: str):
    from app.services.kb_service import KnowledgeBase

    return KnowledgeBase(id=kb_id, name=kb_id, collectionName=collection)


def test_search_skips_collections_not_yet_created() -> None:
    kb_a = make_kb("a", "col_a")
    service = make_search_service([kb_a], existing=set(), results={})
    assert service.search("query") == []


def test_search_tags_kb_info_and_merges() -> None:
    kb_a = make_kb("a", "col_a")
    kb_b = make_kb("b", "col_b")
    results = {
        "col_a": [{"text": "A1", "docId": "d1", "chunkIndex": 0}],
        "col_b": [{"text": "B1", "docId": "d2", "chunkIndex": 0}],
    }
    service = make_search_service([kb_a, kb_b], existing={"col_a", "col_b"}, results=results)
    hits = service.search("query", top_k=2)

    assert [call["collection"] for call in service._vector.calls] == ["col_a", "col_b"]
    assert [h["text"] for h in hits] == ["A1", "B1"]
    assert hits[0]["kbId"] == "a" and hits[0]["kbName"] == "a"


def test_search_with_doc_scope_applies_filter() -> None:
    kb_a = make_kb("a", "col_a")
    service = make_search_service([kb_a], existing={"col_a"}, results={"col_a": []})
    service.search("query", kb_id="a", doc_id="doc-9", top_k=3)
    assert service._vector.calls[0]["filter"] == 'doc_id == "doc-9"'
    service.search("query", kb_id="a", top_k=3)
    assert service._vector.calls[1]["filter"] == ""


def test_debug_search_returns_three_channels() -> None:
    kb_a = make_kb("a", "col_a")
    results = {"col_a": [{"text": "H", "docId": "d1", "chunkIndex": 0}]}
    service = make_search_service([kb_a], existing={"col_a"}, results=results)
    out = service.debug_search("query", kb_id="a", top_k=2)

    assert set(out) == {"hybrid", "dense", "sparse"}
    assert out["hybrid"][0]["kbId"] == "a"
    assert all(len(channel) == 1 for channel in out.values())


def test_search_single_kb_not_found() -> None:
    service = make_search_service([], existing=set(), results={})
    with pytest.raises(KbNotFoundError):
        service.search("query", kb_id="missing")
