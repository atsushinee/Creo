"""Request/response models for the chat and session APIs."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128, examples=["3f9c2a6e-..."])
    message: str = Field(min_length=1, max_length=32_000, examples=["计算 123 * 456"])
    # Document-chat scope (ADR-0004 Update 3): when both are set, the run is
    # bound to a document-scoped agent whose retrieval is filtered to that doc.
    kb_id: str | None = Field(default=None, max_length=64)
    doc_id: str | None = Field(default=None, max_length=64)


class ToolRecord(BaseModel):
    toolCallId: str
    toolName: str
    args: Any = None
    result: Any = None
    isError: bool = False


class HistoryMessage(BaseModel):
    """A reconstructed message for session history (protocol-neutral)."""

    id: str
    role: Literal["user", "assistant"]
    content: str
    tools: list[ToolRecord] = Field(default_factory=list)


class SessionOut(BaseModel):
    id: str
    title: str
    createdAt: str
    updatedAt: str


class HealthOut(BaseModel):
    status: Literal["ok"]
    service: str = "creo-backend"
    version: str
    model: str
    agent: Literal["ready", "pending"]
