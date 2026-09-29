"""API tests: SSE endpoint, sessions endpoints, health — runtime is stubbed."""

import json

from fastapi.testclient import TestClient

from app.main import create_app
from app.models.events import (
    ErrorEvent,
    MessageDelta,
    MessageEnd,
    MessageStart,
    RunFinished,
    RunStarted,
    ToolResult,
    ToolStart,
)


class StubRuntime:
    """Replaces the real runtime at app.state for deterministic API tests."""

    status = "ready"

    def __init__(self, events=None, history=None) -> None:
        self._events = events or []
        self._history = history or []
        self.scoped_calls: list[tuple | None] = []
        self.trace: list[dict] = [{"ts": "2026-09-30T00:00:00+00:00", "type": "run_started"}]

    async def stream_events(self, session_id: str, message: str, *, doc_scope=None):
        self.scoped_calls.append(doc_scope)
        for event in self._events:
            yield event

    async def get_history(self, session_id: str, *, doc_scope=None):
        return self._history

    def get_session_trace(self, session_id: str):
        return self.trace


def parse_sse(text: str) -> list[tuple[str, dict]]:
    frames = []
    for frame in text.split("\n\n"):
        if not frame.strip():
            continue
        event_line = next(line for line in frame.split("\n") if line.startswith("event: "))
        data_line = next(line for line in frame.split("\n") if line.startswith("data: "))
        payload = json.loads(data_line.removeprefix("data: "))
        frames.append((event_line.removeprefix("event: "), payload))
    return frames


def test_health() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["agent"] in {"ready", "pending"}
        assert body["model"]


def test_chat_streams_sse_frames_in_order() -> None:
    stub = StubRuntime(
        events=[
            RunStarted(runId="r1"),
            MessageStart(messageId="m1"),
            MessageDelta(messageId="m1", content="56088"),
            MessageEnd(messageId="m1"),
            ToolStart(toolCallId="c1", toolName="calculator", args={}),
            ToolResult(toolCallId="c1", result="ok"),
            RunFinished(runId="r1"),
        ]
    )
    with TestClient(create_app()) as client:
        client.app.state.agent_runtime = stub
        response = client.post("/api/chat", json={"session_id": "s1", "message": "hi"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"

    frames = parse_sse(response.text)
    assert [name for name, _ in frames] == [
        "run_started",
        "message_start",
        "message_delta",
        "message_end",
        "tool_start",
        "tool_result",
        "run_finished",
    ]
    assert frames[0][1] == {"type": "run_started", "runId": "r1"}
    assert frames[2][1] == {"type": "message_delta", "messageId": "m1", "content": "56088"}


def test_chat_validation_error() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/api/chat", json={"session_id": "", "message": ""})
    assert response.status_code == 422


def test_chat_registers_session_with_derived_title() -> None:
    with TestClient(create_app()) as client:
        stub = StubRuntime(events=[RunStarted(runId="r"), RunFinished(runId="r")])
        client.app.state.agent_runtime = stub
        client.post("/api/chat", json={"session_id": "sess-1", "message": "帮我计算 123 * 456"})
        listing = client.get("/api/sessions").json()
    assert len(listing) == 1
    assert listing[0]["id"] == "sess-1"
    assert listing[0]["title"] == "帮我计算 123 * 456"
    assert stub.scoped_calls[-1] is None  # plain chat: no document scope


def test_chat_document_scope_reaches_runtime() -> None:
    with TestClient(create_app()) as client:
        stub = StubRuntime(events=[RunStarted(runId="r"), RunFinished(runId="r")])
        client.app.state.agent_runtime = stub
        response = client.post(
            "/api/chat",
            json={"session_id": "s-doc", "message": "总结这份文件", "kb_id": "kb1", "doc_id": "d1"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
    assert stub.scoped_calls[-1] == ("kb1", "d1")


def test_error_event_reaches_client() -> None:
    stub = StubRuntime(
        events=[RunStarted(runId="r"), ErrorEvent(message="boom"), RunFinished(runId="r")]
    )
    with TestClient(create_app()) as client:
        client.app.state.agent_runtime = stub
        response = client.post("/api/chat", json={"session_id": "s", "message": "hi"})
    frames = parse_sse(response.text)
    assert frames[1][1]["message"] == "boom"


def test_session_trace_endpoint() -> None:
    with TestClient(create_app()) as client:
        client.app.state.agent_runtime = StubRuntime()
        response = client.get("/api/sessions/sess-9/trace")
        assert response.status_code == 200
        body = response.json()
        assert body[0]["type"] == "run_started"


def test_session_messages_endpoint() -> None:
    from app.models.chat import HistoryMessage, ToolRecord

    history = [
        HistoryMessage(id="1", role="user", content="hi"),
        HistoryMessage(
            id="2",
            role="assistant",
            content="done",
            tools=[ToolRecord(toolCallId="c1", toolName="calculator", args={}, result="42")],
        ),
    ]
    with TestClient(create_app()) as client:
        client.app.state.agent_runtime = StubRuntime(history=history)
        client.post("/api/chat", json={"session_id": "sess-9", "message": "hi"})
        response = client.get("/api/sessions/sess-9/messages")
        assert response.status_code == 200
        body = response.json()
        assert body[1]["tools"][0]["result"] == "42"
        assert client.get("/api/sessions/missing/messages").status_code == 404


def test_delete_session() -> None:
    with TestClient(create_app()) as client:
        client.post("/api/chat", json={"session_id": "sess-x", "message": "hi"})
        assert client.delete("/api/sessions/sess-x").status_code == 204
        assert client.delete("/api/sessions/sess-x").status_code == 404
