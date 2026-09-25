"""Tests for the SSE encoder and event models (protocol contract)."""

import json

from app.api.sse import encode_sse
from app.models.events import (
    MessageDelta,
    RunFinished,
    RunStarted,
    ToolResult,
    ToolStart,
)


def test_run_started_frame() -> None:
    frame = encode_sse(RunStarted(runId="r1"))
    event_type, data = _parse(frame)
    assert event_type == "run_started"
    assert data == {"type": "run_started", "runId": "r1"}


def test_message_delta_frame() -> None:
    event_type, data = _parse(encode_sse(MessageDelta(messageId="m1", content="你好")))
    assert event_type == "message_delta"
    assert data["messageId"] == "m1"
    assert data["content"] == "你好"


def test_tool_events_frames() -> None:
    start_type, start_data = _parse(
        encode_sse(
            ToolStart(toolCallId="c1", toolName="calculator", args={"expression": "123*456"})
        )
    )
    assert start_type == "tool_start"
    assert start_data["args"] == {"expression": "123*456"}

    result_type, result_data = _parse(
        encode_sse(ToolResult(toolCallId="c1", result="56088", isError=True))
    )
    assert result_type == "tool_result"
    assert result_data["isError"] is True


def test_frame_ends_with_blank_line() -> None:
    frame = encode_sse(RunFinished(runId="r1"))
    assert frame.endswith("\n\n")
    assert frame.count("\n\n") == 1


def _parse(frame: str) -> tuple[str, dict]:
    lines = frame.strip("\n").split("\n")
    event_line = next(line for line in lines if line.startswith("event: "))
    data_line = next(line for line in lines if line.startswith("data: "))
    return event_line.removeprefix("event: "), json.loads(data_line.removeprefix("data: "))
