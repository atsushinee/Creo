"""AgentRuntime: runs the DeepAgents graph and translates its raw stream into
Creo Agent Events.

This is the single translation layer between the agent framework and the Creo
Agent Event Protocol (docs/decisions/0002-agent-event-protocol.md). Nothing
downstream (API routes, frontend) sees LangChain / LangGraph objects.

Stream shapes verified against deepagents 0.7.18 / langgraph 1.2.12
(docs/development/TECHNICAL-NOTES.md):

- with `stream_mode=["messages", "updates"], subgraphs=True`, each yielded
  item is a 3-tuple `(namespace, mode, payload)`;
- `messages` payload is `(chunk, metadata)` where chunk is an AIMessageChunk
  (token deltas; a final empty chunk carries `chunk_position="last"`) or a
  full ToolMessage;
- `updates` payload is `{node_name: state_delta}`; the `model` node delta
  contains the complete AIMessage (with fully parsed `tool_calls`), the
  `tools` node delta contains ToolMessage(s).
"""

import json
from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from app.core.logging import get_logger
from app.models.chat import HistoryMessage, ToolRecord
from app.models.events import (
    AgentEvent,
    ErrorEvent,
    MessageDelta,
    MessageEnd,
    MessageStart,
    RunFinished,
    RunStarted,
    ThinkingDelta,
    ToolResult,
    ToolStart,
)

logger = get_logger("agent.runtime")


def extract_text(content: Any) -> str:
    """Message content may be a plain string or a list of content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return ""


def extract_reasoning(chunk: Any) -> str:
    """Reasoning text from reasoning-model chunks (ADR-0002 Update 1).

    Two shapes seen in the wild: OpenAI-compatible endpoints stream it as
    `additional_kwargs.reasoning_content` (DashScope/Qwen, DeepSeek-R1, …);
    Anthropic-style providers emit thinking content blocks.
    """
    kwargs = getattr(chunk, "additional_kwargs", None) or {}
    reasoning = kwargs.get("reasoning_content") or kwargs.get("reasoning")
    if isinstance(reasoning, str):
        return reasoning
    content = getattr(chunk, "content", None)
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") in ("thinking", "reasoning"):
                text = block.get("thinking") or block.get("reasoning") or block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def _tool_payload(content: Any) -> Any:
    """Prefer extracted text; keep structured payloads instead of dropping them."""
    if isinstance(content, str):
        return content
    text = extract_text(content)
    return text if text else content


class AgentRuntime:
    """Lazily builds the agent graph and exposes protocol-level operations."""

    def __init__(
        self,
        agent_builder: Callable[[], Any],
        doc_agent_builder: Callable[[str, str], Callable[[], Any]] | None = None,
    ) -> None:
        self._agent_builder = agent_builder
        self._doc_agent_builder = doc_agent_builder
        self._agent: Any | None = None
        self._doc_agents: dict[tuple[str, str], Any] = {}

    @property
    def status(self) -> str:
        """'ready' once the graph is built, 'pending' before the first run."""
        return "ready" if self._agent is not None else "pending"

    def _ensure_agent(self) -> Any:
        if self._agent is None:
            self._agent = self._agent_builder()
        return self._agent

    def _scoped_agent(self, doc_scope: tuple[str, str]) -> Any:
        """One graph (and memory) per (kb_id, doc_id) document-chat scope."""
        if doc_scope not in self._doc_agents:
            if self._doc_agent_builder is None:
                raise RuntimeError("document chat is not configured")
            self._doc_agents[doc_scope] = self._doc_agent_builder(*doc_scope)()
        return self._doc_agents[doc_scope]

    async def stream_events(
        self,
        session_id: str,
        message: str,
        *,
        doc_scope: tuple[str, str] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Run one agent turn and yield Creo Agent Events.

        Any failure (model construction, provider error, tool node crash)
        surfaces as an `error` event; the stream always ends with
        `run_finished` unless the client disconnects. With `doc_scope` set,
        the document-scoped graph is used (doc-chat mode).
        """
        run_id = uuid4().hex
        converter = _EventConverter()
        yield RunStarted(runId=run_id)
        try:
            agent = self._scoped_agent(doc_scope) if doc_scope else self._ensure_agent()
            config = {"configurable": {"thread_id": session_id}}
            async for _ns, mode, payload in agent.astream(
                {"messages": [{"role": "user", "content": message}]},
                config=config,
                stream_mode=["messages", "updates"],
                subgraphs=True,
            ):
                for event in converter.convert(mode, payload):
                    yield event
        except Exception as exc:
            logger.exception("agent run failed (session=%s)", session_id)
            yield ErrorEvent(message=f"{type(exc).__name__}: {exc}")
        for event in converter.finish():
            yield event
        yield RunFinished(runId=run_id)

    async def get_history(
        self, session_id: str, *, doc_scope: tuple[str, str] | None = None
    ) -> list[HistoryMessage]:
        """Reconstruct protocol-neutral history from the checkpointer state."""
        agent = self._scoped_agent(doc_scope) if doc_scope else self._ensure_agent()
        snapshot = await agent.aget_state({"configurable": {"thread_id": session_id}})
        messages = (snapshot.values or {}).get("messages", []) if snapshot.values else []
        return messages_to_history(messages)


class _EventConverter:
    """Stateful per-run translator from raw stream items to Agent Events."""

    def __init__(self) -> None:
        self._open_source_id: str | None = None
        self._open_message_id: str | None = None
        self._tool_calls_started: set[str] = set()
        self._tool_results_seen: set[str] = set()

    def convert(self, mode: str, payload: Any) -> list[AgentEvent]:
        if mode == "messages":
            return self._convert_messages(payload)
        if mode == "updates":
            return self._convert_updates(payload)
        return []

    def finish(self) -> list[AgentEvent]:
        return self._close_message()

    # --- messages mode: payload = (chunk, metadata) -----------------------

    def _convert_messages(self, payload: Any) -> list[AgentEvent]:
        chunk = payload[0]
        if isinstance(chunk, ToolMessage):
            return self._tool_result(chunk)
        if not isinstance(chunk, AIMessageChunk):
            return []
        events: list[AgentEvent] = []
        reasoning = extract_reasoning(chunk)
        text = extract_text(chunk.content)
        if reasoning or text:
            events.extend(self._open_message(chunk.id))
        if reasoning:
            assert self._open_message_id is not None
            events.append(ThinkingDelta(content=reasoning))
        if text:
            assert self._open_message_id is not None
            events.append(MessageDelta(messageId=self._open_message_id, content=text))
        if getattr(chunk, "chunk_position", None) == "last":
            events.extend(self._close_message())
        return events

    # --- updates mode: payload = {node: state_delta} ----------------------

    def _convert_updates(self, payload: Any) -> list[AgentEvent]:
        events: list[AgentEvent] = []
        if not isinstance(payload, dict):
            return events
        for delta in payload.values():
            if not isinstance(delta, dict):
                continue
            for msg in delta.get("messages") or []:
                if isinstance(msg, AIMessage):
                    events.extend(self._tool_starts(msg))
                elif isinstance(msg, ToolMessage):
                    events.extend(self._tool_result(msg))
        return events

    # --- message lifecycle -------------------------------------------------

    def _open_message(self, source_id: str | None) -> list[AgentEvent]:
        same_message = self._open_message_id is not None and (
            source_id is None or source_id == self._open_source_id
        )
        if same_message:
            return []
        events = self._close_message()
        self._open_message_id = uuid4().hex
        self._open_source_id = source_id
        events.append(MessageStart(messageId=self._open_message_id))
        return events

    def _close_message(self) -> list[AgentEvent]:
        if self._open_message_id is None:
            return []
        event = MessageEnd(messageId=self._open_message_id)
        self._open_message_id = None
        self._open_source_id = None
        return [event]

    # --- tools --------------------------------------------------------------

    def _tool_starts(self, message: AIMessage) -> list[AgentEvent]:
        if not message.tool_calls:
            return []
        events = self._close_message()
        for call in message.tool_calls:
            call_id = str(call.get("id") or uuid4().hex)
            if call_id in self._tool_calls_started:
                continue
            self._tool_calls_started.add(call_id)
            events.append(
                ToolStart(
                    toolCallId=call_id,
                    toolName=str(call.get("name", "unknown_tool")),
                    args=_parsed_args(call.get("args")),
                )
            )
        return events

    def _tool_result(self, message: ToolMessage) -> list[AgentEvent]:
        call_id = message.tool_call_id
        if not call_id or call_id in self._tool_results_seen:
            return []
        self._tool_results_seen.add(call_id)
        is_error = getattr(message, "status", "success") == "error"
        return [
            ToolResult(
                toolCallId=call_id,
                result=_tool_payload(message.content),
                isError=is_error,
            )
        ]


def _parsed_args(args: Any) -> Any:
    if isinstance(args, str):
        try:
            return json.loads(args) if args.strip() else {}
        except json.JSONDecodeError:
            return args
    return args if args is not None else {}


def messages_to_history(messages: list[Any]) -> list[HistoryMessage]:
    """Map checkpointer messages to protocol-neutral history entries.

    ToolMessages are folded into the preceding assistant entry's tool records.
    """
    history: list[HistoryMessage] = []
    last_assistant: HistoryMessage | None = None

    for msg in messages:
        if isinstance(msg, HumanMessage):
            entry = HistoryMessage(
                id=str(msg.id or uuid4().hex),
                role="user",
                content=extract_text(msg.content),
            )
            history.append(entry)
            last_assistant = None
        elif isinstance(msg, AIMessage):
            tools = [
                ToolRecord(
                    toolCallId=str(call.get("id") or uuid4().hex),
                    toolName=str(call.get("name", "unknown_tool")),
                    args=_parsed_args(call.get("args")),
                )
                for call in msg.tool_calls
            ]
            entry = HistoryMessage(
                id=str(msg.id or uuid4().hex),
                role="assistant",
                content=extract_text(msg.content),
                tools=tools,
            )
            history.append(entry)
            last_assistant = entry if tools else None
        elif isinstance(msg, ToolMessage):
            if last_assistant is None:
                continue
            for record in reversed(last_assistant.tools):
                if record.toolCallId == msg.tool_call_id:
                    record.result = _tool_payload(msg.content)
                    record.isError = getattr(msg, "status", "success") == "error"
                    break

    return history
