"""Knowledge base retrieval tool (ADR-0004).

Factory pattern: the agent registers the returned tool; the KbSearchService is
injected at composition time (main.py lifespan), so the tool stays independent
of FastAPI and of storage details. langchain_core (not deepagents/langchain)
is fine here — the boundary rule only forbids the bare framework modules.
"""

from typing import Any

from langchain_core.tools import tool


def make_kb_search_tool(searcher: Any, *, default_top_k: int = 5):
    """Build the search_knowledge_base tool bound to a KbSearchService."""

    @tool
    def search_knowledge_base(
        query: str, kb_id: str | None = None, top_k: int = default_top_k
    ) -> str:
        """Search the user's uploaded documents (knowledge base) for relevant
        passages. Returns the top matching text chunks with numbered citations
        like [1] filename (page N). Use this whenever the user asks about the
        content of documents they uploaded, or when you need grounded facts
        from their files. Leave kb_id empty to search all knowledge bases."""
        try:
            top = int(top_k)
        except (TypeError, ValueError):
            top = default_top_k
        top = max(1, min(top, 20))
        try:
            hits = searcher.search(query, kb_id=kb_id, top_k=top)
        except Exception as exc:
            raise ValueError(f"knowledge base search failed: {exc}") from exc
        if not hits:
            return "No relevant content found in the knowledge base."
        lines: list[str] = []
        for index, hit in enumerate(hits, start=1):
            meta = hit.get("metadata") or {}
            filename = meta.get("filename") or hit.get("kbName") or "document"
            page = hit.get("page") or 0
            source = f"{filename} (page {page})" if page else str(filename)
            lines.append(f"[{index}] {source}\n{hit.get('text', '')}")
        return "\n\n".join(lines)

    return search_knowledge_base


def make_doc_search_tool(searcher: Any, *, kb_id: str, doc_id: str):
    """Document-scoped variant for doc-chat mode (ADR-0004 Update 3).

    The scope is closed over, not exposed to the model: every retrieval is
    filtered to exactly one document, and the tool name/description tell the
    agent that answers must come from that document only.
    """

    @tool
    def search_document(query: str, top_k: int = 5) -> str:
        """Search THIS document (the one the user is chatting about) for the
        passages relevant to the query. Returns top matches with numbered
        citations like [1] (page N). Every factual claim must come from here;
        if the document does not contain the answer, say so explicitly."""
        try:
            top = int(top_k)
        except (TypeError, ValueError):
            top = 5
        top = max(1, min(top, 20))
        try:
            hits = searcher.search(query, kb_id=kb_id, doc_id=doc_id, top_k=top)
        except Exception as exc:
            raise ValueError(f"document search failed: {exc}") from exc
        if not hits:
            return "No relevant passage found in this document."
        lines: list[str] = []
        for index, hit in enumerate(hits, start=1):
            page = hit.get("page") or 0
            source = f"(page {page})" if page else ""
            lines.append(f"[{index}]{source}\n{hit.get('text', '')}")
        return "\n\n".join(lines)

    return search_document
