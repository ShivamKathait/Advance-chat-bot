import hashlib
import os
import uuid

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.core.logging import logger_adapter
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentListResponse, DocumentResponse, DocumentStatusResponse
from app.services.minio_service import MinioService
from app.core.security import sanitize_input
from app.services.vector_service import vector_store
from app.workers.ingestion_worker import enqueue_ingestion

class DocumentService:
    def __init__(self, minio_service: MinioService, repository: DocumentRepository):
        self.minio_service = minio_service
        self.repository = repository

    async def upload_document(self, file: UploadFile) -> DocumentResponse:
        """
        Validate and upload a document, then enqueue it for background ingestion.

        Returns immediately with status='pending' — the caller should poll
        GET /documents/{id}/status for progress.
        """
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must have a name",
            )

        file_content = await file.read()

        if len(file_content) > settings.MAX_DOCUMENT_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {settings.MAX_DOCUMENT_SIZE} bytes",
            )

        file_name = sanitize_input(file.filename, max_length=255)
        file_type = os.path.splitext(file_name)[1].lower()

        if file_type not in settings.ALLOWED_FILE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not supported. Allowed: {settings.ALLOWED_FILE_TYPES}",
            )

        content_hash = hashlib.sha256(file_content).hexdigest()
        existing = self.repository.get_by_content_hash(content_hash)
        if existing is not None:
            logger_adapter.info(
                "Duplicate upload detected, reusing existing document",
                document_id=str(existing.id),
                content_hash=content_hash,
            )
            return DocumentResponse(
                id=str(existing.id),
                filename=existing.file_name,
                file_type=existing.file_type,
                status=existing.status,
                num_chunks=existing.num_chunks,
                message="Identical file already ingested — reusing existing document.",
            )

        document_id = uuid.uuid4()
        storage_key = f"documents/{document_id}{file_type}"

        # Create DB record first so we have a stable ID before touching external storage.
        document = self.repository.create(
            id=document_id,
            filename=file_name,
            file_type=file_type,
            storage_key=storage_key,
            content_hash=content_hash,
            status="pending",
        )

        try:
            self.minio_service.upload_bytes(
                bucket=settings.MINIO_BUCKET,
                key=storage_key,
                data=file_content,
                content_type=file.content_type or "application/octet-stream",
            )
        except Exception as exc:
            self.repository.update_status(document_id, "failed", error_message=str(exc))
            logger_adapter.error(
                "MinIO upload failed",
                document_id=str(document_id),
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="File storage unavailable. Please try again.",
            )

        logger_adapter.info(
            "Document uploaded to storage",
            document_id=str(document_id),
            file_name=file_name,
            file_size=len(file_content),
        )

        # Durably queue ingestion via ARQ/Redis — survives API process restarts,
        # unlike an in-process asyncio task which would be silently abandoned.
        await enqueue_ingestion(
            document_id=str(document_id),
            storage_key=storage_key,
            file_type=file_type,
            metadata={"filename": file_name},
        )
        self.repository.update_status(document_id, "queued")

        return DocumentResponse(
            id=str(document.id),
            filename=document.file_name,
            file_type=document.file_type,
            status="queued",
            num_chunks=document.num_chunks,
            message="Document uploaded. Processing in background.",
        )

    async def get_status(self, document_id: uuid.UUID) -> DocumentStatusResponse:
        """Return the current ingestion status for a document."""
        document = self.repository.get_by_id(document_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )
        return DocumentStatusResponse(
            id=str(document.id),
            status=document.status,
            num_chunks=document.num_chunks,
            error_message=document.error_message,
        )

    async def list_documents(self) -> DocumentListResponse:
        """
        List all uploaded documents
        
        Returns:
            List of documents in vector store
        """
        try:
            documents, total = self.repository.list(skip=0, limit=20)
            return DocumentListResponse(
                documents=[DocumentResponse.model_validate(doc) for doc in documents],
                total=total,
            )
        except Exception as e:
            logger_adapter.error("Error listing documents", error=str(e))
            raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving documents"
        )

    async def delete_document(self, document_id: uuid.UUID):
        """
        Delete a document: removes the Postgres record, Qdrant chunks,
        the MinIO file, and the Redis BM25 corpus entry.

        Args:
            document_id: Document ID to delete

        Returns:
            Success message
        """
        document = self.repository.get_by_id(document_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        try:
            storage_key = document.storage_key
            self.repository.delete_by_id(document_id)
            await vector_store.remove_document(document_id)

            try:
                self.minio_service.delete_object(bucket=settings.MINIO_BUCKET, key=storage_key)
            except Exception as e:
                logger_adapter.warning(f"MinIO cleanup failed (non-fatal): {e}")

            try:
                r = await vector_store._get_redis()
                bm25_key = f"bm25:doc:{document_id}"
                await r.delete(bm25_key)
                await r.srem("bm25:doc_keys", bm25_key)
            except Exception as e:
                logger_adapter.warning(f"Redis BM25 cleanup failed (non-fatal): {e}")

            logger_adapter.info("Document deleted successfully", document_id=document_id)
            return {
                "status": "success",
                "message": f"Document {document_id} deleted",
                "document_id": document_id,
            }
        except Exception as e:
            logger_adapter.error("Error deleting document", document_id=document_id, error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error deleting document",
            )