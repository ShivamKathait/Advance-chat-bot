import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.services import get_document_service, get_document_repository
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentDeleteResponse, DocumentListResponse, DocumentResponse, DocumentStatusResponse
from app.services.document_service import DocumentService
from app.services.vector_service import vector_store
from app.workers.ingestion_worker import enqueue_ingestion

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])


@router.post("/upload", response_model=DocumentResponse, status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    service: DocumentService = Depends(get_document_service),
):
    """
    Upload a document and enqueue it for background ingestion.

    Returns 202 Accepted immediately — poll GET /documents/{id}/status for progress.
    """
    return await service.upload_document(file)


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: uuid.UUID,
    service: DocumentService = Depends(get_document_service),
):
    """
    Poll the ingestion status of a previously uploaded document.

    Status values: pending → queued → processing → completed | failed
    """
    return await service.get_status(document_id)

@router.get("/list", response_model=DocumentListResponse)
async def list_documents(service: DocumentService = Depends(get_document_service)):
    return await service.list_documents()

@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
async def delete_documents(
    document_id: str,
    service: DocumentService = Depends(get_document_service),
):
    return await service.delete_document(document_id)


@router.post("/{document_id}/reingest", status_code=202)
async def reingest_document(
    document_id: str,
    repo: DocumentRepository = Depends(get_document_repository),
    db: Session = Depends(get_db),
):
    """
    Delete existing chunks from Qdrant and the BM25 Redis corpus, then re-enqueue
    the document for ingestion with the current config (e.g. CONTEXTUAL_ENRICHMENT_ENABLED).

    Useful after toggling CONTEXTUAL_ENRICHMENT_ENABLED so existing docs benefit
    from the richer embeddings without a manual delete + re-upload.
    """
    doc_uuid = uuid.UUID(document_id)
    doc = repo.get_by_id(doc_uuid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove old vectors from Qdrant
    await vector_store.remove_document(document_id)

    # Remove from BM25 Redis corpus
    try:
        r = await vector_store._get_redis()
        bm25_key = f"bm25:doc:{document_id}"
        await r.delete(bm25_key)
        await r.srem("bm25:doc_keys", bm25_key)
    except Exception:
        pass  # non-fatal if Redis is unavailable

    # Reset status and re-enqueue
    repo.update_status(doc_uuid, "pending", num_chunks=0)
    await enqueue_ingestion(
        document_id=document_id,
        storage_key=doc.storage_key,
        file_type=doc.file_type,
        metadata={"filename": doc.file_name},
    )

    return {"status": "reingestion_queued", "document_id": document_id, "filename": doc.file_name}