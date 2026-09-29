"""Creo Agent Event Protocol — single source of truth.

Frontend mirror: frontend/src/types/agent.ts (must be kept in sync).
See docs/decisions/0002-agent-event-protocol.md before extending.
"""

from typing import Any, Literal

from pydantic import BaseModel

EventType = Literal[
    "run_started",
    "message_start",
    "message_delta",
    "message_end",
    "thinking_delta",
    "tool_start",
    "tool_result",
    "error",
    "run_finished",
]

# Reserved for future phases — do not emit yet (update ADR-0002 first):
# "approval_required", "state_update", "artifact_created", "artifact_updated",
# "source_added", "agent_status"


class RunStarted(BaseModel):
    type: Literal["run_started"] = "run_started"
    runId: str


class MessageStart(BaseModel):
    type: Literal["message_start"] = "message_start"
    messageId: str


class MessageDelta(BaseModel):
    type: Literal["message_delta"] = "message_delta"
    messageId: str
    content: str


class MessageEnd(BaseModel):
    type: Literal["message_end"] = "message_end"
    messageId: str


class ThinkingDelta(BaseModel):
    """Reasoning-model thinking increment (ADR-0002 Update 1). Frontend
    attaches it to the current streaming assistant message."""

    type: Literal["thinking_delta"] = "thinking_delta"
    content: str


class ToolStart(BaseModel):
    type: Literal["tool_start"] = "tool_start"
    toolCallId: str
    toolName: str
    args: Any = None


class ToolResult(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    toolCallId: str
    result: Any = None
    isError: bool = False


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


class RunFinished(BaseModel):
    type: Literal["run_finished"] = "run_finished"
    runId: str


AgentEvent = (
    RunStarted
    | MessageStart
    | MessageDelta
    | MessageEnd
    | ThinkingDelta
    | ToolStart
    | ToolResult
    | ErrorEvent
    | RunFinished
)
