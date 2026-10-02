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


class SearchTestRequest(BaseModel):
    query: str = Field(min_length=1, max_length=512, examples=["公司的经营范围是什么"])
    top_k: int = Field(default=5, ge=1, le=20)
    doc_id: str | None = Field(default=None, max_length=64)


class ParseElementOut(BaseModel):
    type: str
    text: str
    pageNumber: int
    tableHtml: str | None = None
    coordinates: dict | None = None


class ParseResultOut(BaseModel):
    available: bool
    source: str | None = None
    profile: str | None = None
    elements: list[ParseElementOut] = Field(default_factory=list)


class DocChunkOut(BaseModel):
    text: str
    chunkIndex: int
    page: int
