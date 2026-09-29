"""Knowledge base endpoints (ADR-0004): KB/document management + PDF upload.

Routes only validate, persist via the KnowledgeService and schedule the
ingestion pipeline on BackgroundTasks — no parsing or vector logic here.
"""

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile

from app.api.deps import get_ingestion_service, get_knowledge_service, get_vector_store_service
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.knowledge import KbDocumentOut, KnowledgeBaseCreateRequest, KnowledgeBaseOut
from app.services.ingestion_service import IngestionService
from app.services.kb_service import DuplicateDocumentError, KnowledgeService, UploadTooLargeError

router = APIRouter(tags=["knowledge"])
logger = get_logger("api.knowledge")

KbDep = Annotated[KnowledgeService | None, Depends(get_knowledge_service)]
IngestionDep = Annotated[IngestionService | None, Depends(get_ingestion_service)]
StoreDep = Annotated[Any | None, Depends(get_vector_store_service)]


def _require(service: Any) -> Any:
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="knowledge base is disabled (set CREO_KB_ENABLED=true and configure"
            " CREO_MILVUS_URI / CREO_UNSTRUCTURED_API_KEY / CREO_KB_EMBEDDING_BASE_URL)",
        )
    return service


def _require_kb(service: KnowledgeService, kb_id: str) -> Any:
    kb = service.get_kb(kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="knowledge base not found")
    return kb


def _kb_out(service: KnowledgeService, kb: Any) -> KnowledgeBaseOut:
    return KnowledgeBaseOut(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        collectionName=kb.collectionName,
        documentCount=service.count_documents(kb.id),
        createdAt=kb.createdAt.isoformat(),
    )


def _doc_out(doc: Any) -> KbDocumentOut:
    return KbDocumentOut(
        id=doc.id,
        kbId=doc.kbId,
        filename=doc.filename,
        size=doc.size,
        status=doc.status,
        error=doc.error,
        chunkCount=doc.chunkCount,
        createdAt=doc.createdAt.isoformat(),
        updatedAt=doc.updatedAt.isoformat(),
    )


@router.post("/kb", status_code=201)
async def create_kb(
    request: KnowledgeBaseCreateRequest,
    kb_service: KbDep,
) -> KnowledgeBaseOut:
    service = _require(kb_service)
    kb = service.create_kb(request.name.strip(), request.description.strip())
    return _kb_out(service, kb)


@router.get("/kb")
async def list_kbs(kb_service: KbDep) -> list[KnowledgeBaseOut]:
    service = _require(kb_service)
    return [_kb_out(service, kb) for kb in service.list_kbs()]


@router.delete("/kb/{kb_id}", status_code=204)
async def delete_kb(kb_id: str, kb_service: KbDep, store: StoreDep) -> None:
    service = _require(kb_service)
    vector_store = _require(store)
    kb = _require_kb(service, kb_id)
    vector_store.drop_collection(kb.collectionName)
    service.delete_kb(kb_id)
    logger.info("deleted knowledge base id=%s", kb_id)


@router.post("/kb/{kb_id}/documents", status_code=201)
async def upload_document(
    kb_id: str,
    file: UploadFile,
    background: BackgroundTasks,
    kb_service: KbDep,
    ingestion: IngestionDep,
) -> KbDocumentOut:
    service = _require(kb_service)
    ingestion_service = _require(ingestion)
    kb = _require_kb(service, kb_id)

    filename = file.filename or "document.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="only PDF files are supported")

    settings = get_settings()
    try:
        doc = await asyncio.to_thread(
            service.save_upload,
            kb.id,
            filename,
            file.file,
            max_bytes=settings.kb_upload_max_bytes,
        )
    except DuplicateDocumentError as exc:
        raise HTTPException(
            status_code=409, detail="identical file already uploaded to this knowledge base"
        ) from exc
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    # Sync callable → BackgroundTasks runs it in the worker threadpool after
    # the response, keeping the event loop free for streaming chats.
    background.add_task(ingestion_service.ingest, doc.id)
    logger.info("accepted upload kb=%s doc=%s size=%d", kb.id, doc.id, doc.size)
    return _doc_out(doc)


@router.get("/kb/{kb_id}/documents")
async def list_documents(kb_id: str, kb_service: KbDep) -> list[KbDocumentOut]:
    service = _require(kb_service)
    _require_kb(service, kb_id)
    return [_doc_out(doc) for doc in service.list_documents(kb_id)]


@router.delete("/kb/{kb_id}/documents/{doc_id}", status_code=204)
async def delete_document(
    kb_id: str, doc_id: str, kb_service: KbDep, store: StoreDep
) -> None:
    service = _require(kb_service)
    vector_store = _require(store)
    kb = _require_kb(service, kb_id)
    doc = service.get_document(doc_id)
    if doc is None or doc.kbId != kb.id:
        raise HTTPException(status_code=404, detail="document not found")
    if doc.status == "processing":
        raise HTTPException(status_code=409, detail="document is currently processing")
    vector_store.delete_doc(kb.collectionName, doc.id)
    service.delete_document(doc.id)


@router.post("/kb/{kb_id}/documents/{doc_id}/reingest", status_code=202)
async def reingest_document(
    kb_id: str,
    doc_id: str,
    background: BackgroundTasks,
    kb_service: KbDep,
    ingestion: IngestionDep,
) -> KbDocumentOut:
    service = _require(kb_service)
    ingestion_service = _require(ingestion)
    kb = _require_kb(service, kb_id)
    doc = service.get_document(doc_id)
    if doc is None or doc.kbId != kb.id:
        raise HTTPException(status_code=404, detail="document not found")
    if doc.status == "processing":
        raise HTTPException(status_code=409, detail="document is currently processing")
    updated = service.update_document_status(doc.id, "pending", error=None)
    background.add_task(ingestion_service.ingest, doc.id)
    assert updated is not None  # fetched by id above
    return _doc_out(updated)
