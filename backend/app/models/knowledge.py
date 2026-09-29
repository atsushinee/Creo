"""Request/response models for the knowledge base APIs (ADR-0004)."""

from typing import Literal

from pydantic import BaseModel, Field

KbDocumentStatus = Literal["pending", "processing", "ready", "failed"]


class KnowledgeBaseCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64, examples=["产品手册"])
    description: str = Field(default="", max_length=512)


class KnowledgeBaseOut(BaseModel):
    id: str
    name: str
    description: str
    collectionName: str
    documentCount: int
    createdAt: str


class KbDocumentOut(BaseModel):
    id: str
    kbId: str
    filename: str
    size: int
    status: KbDocumentStatus
    error: str | None = None
    chunkCount: int = 0
    createdAt: str
    updatedAt: str


class PipelineEventOut(BaseModel):
    id: int
    docId: str
    kbId: str
    stage: str
    status: str
    detail: str | None = None
    durationMs: int | None = None
    createdAt: str
