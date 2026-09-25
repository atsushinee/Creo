"""Minimal SSE frame encoding for the Agent Event stream (ADR-0003).

No sse-starlette dependency on purpose: the frame format is a few lines and
keeps the dependency surface small.
"""

from app.models.events import AgentEvent


def encode_sse(event: AgentEvent) -> str:
    """Render one event as an SSE frame: `event:` + `data:` + blank line."""
    return f"event: {event.type}\ndata: {event.model_dump_json()}\n\n"
