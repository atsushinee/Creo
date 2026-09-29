"""search_knowledge_base tool: citation formatting and error mapping."""

import pytest

from app.tools.knowledge_tools import make_kb_search_tool


class FakeSearcher:
    def __init__(self, hits=None, error=None) -> None:
        self.hits = hits or []
        self.error = error
        self.calls: list[dict] = []

    def search(self, query: str, *, kb_id=None, top_k=5):
        self.calls.append({"query": query, "kb_id": kb_id, "top_k": top_k})
        if self.error is not None:
            raise self.error
        return self.hits


def test_tool_formats_citations() -> None:
    searcher = FakeSearcher(
        hits=[
            {
                "text": "2026 年总资产为 100 亿元。",
                "docId": "d1",
                "chunkIndex": 0,
                "page": 3,
                "metadata": {"filename": "年报.pdf", "type": "NarrativeText"},
                "kbId": "kb1",
                "kbName": "财务",
                "score": 0.9,
            }
        ]
    )
    tool = make_kb_search_tool(searcher)

    result = tool.invoke({"query": "总资产多少"})

    assert "[1] 年报.pdf (page 3)" in result
    assert "2026 年总资产为 100 亿元。" in result
    assert searcher.calls == [{"query": "总资产多少", "kb_id": None, "top_k": 5}]


def test_tool_forwards_kb_id_and_clamps_top_k() -> None:
    searcher = FakeSearcher()
    tool = make_kb_search_tool(searcher)

    tool.invoke({"query": "q", "kb_id": "kb1", "top_k": 99})

    assert searcher.calls == [{"query": "q", "kb_id": "kb1", "top_k": 20}]


def test_tool_empty_result_message() -> None:
    tool = make_kb_search_tool(FakeSearcher(hits=[]))
    result = tool.invoke({"query": "nothing"})
    assert result == "No relevant content found in the knowledge base."


def test_tool_maps_search_errors() -> None:
    tool = make_kb_search_tool(FakeSearcher(error=RuntimeError("milvus down")))
    with pytest.raises(ValueError, match="knowledge base search failed"):
        tool.invoke({"query": "x"})
