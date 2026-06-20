"""
ARQ-based background worker for document ingestion.

Start with:
    arq app.workers.ingestion_worker.WorkerSettings

Each job:
  1. Downloads file bytes from MinIO
  2. Parses → chunks → embeds
  3. Upserts chunks into Qdrant
  4. Stores chunk texts in Redis for BM25 hybrid search
  5. Updates document status in the DB
"""

import json
import uuid
from typing import Any, Dict

from arq.connections import RedisSettings, ArqRedis, create_pool

from app.core.config import settings
from app.core.exceptions import StorageError, ValidationError
from app.core.logging import logger_adapter
from app.db.session import SessionLocal
from app.repositories.document_repository import DocumentRepository
from app.services.minio_service import MinioService
from app.services.Ingestion_service import DocumentIngestionService
from app.services.vector_service import vector_store
import app.models.conversation  # noqa: F401 — registers Conversation + Message with Base's mapper registry
import app.models.feedback      # noqa: F401 — registers Feedback with Base's mapper registry


async def process_ingestion(
    ctx: Dict[str, Any],
    document_id: str,
    storage_key: str,
    file_type: str,
    metadata: Dict[str, Any],
) -> None:
    """
    Background job: parse, chunk, embed, and index a single document.

    Args:
        ctx: ARQ context (holds shared resources from startup)
        document_id: UUID string of the document record
        storage_key: MinIO object key (e.g. 'documents/<uuid>.pdf')
        file_type: File extension including dot (e.g. '.pdf')
        metadata: Arbitrary metadata dict to attach to each chunk
    """
    doc_uuid = uuid.UUID(document_id)

    db = SessionLocal()
    repo = DocumentRepository(db)

    try:
        repo.update_status(doc_uuid, "processing")
        logger_adapter.info("Ingestion job started", document_id=document_id)

        # 1. Download from MinIO
        minio: MinioService = ctx["minio"]
        try:
            file_bytes = minio.download_bytes(bucket=settings.MINIO_BUCKET, key=storage_key)
        except Exception as exc:
            raise StorageError(f"Failed to download {storage_key} from storage: {exc}") from exc
        logger_adapter.info("Downloaded file from storage", document_id=document_id, bytes=len(file_bytes))

        # 2. Parse → chunk → embed
        ingestion_svc: DocumentIngestionService = ctx["ingestion_svc"]
        result = await ingestion_svc.ingest_document(
            file=file_bytes,
            file_type=file_type,
            document_id=document_id,
            metadata=metadata,
        )

        # 3. Upsert into Qdrant
        await vector_store.add_document_chunks(result["chunks"])
        logger_adapter.info(
            "Chunks indexed in Qdrant",
            document_id=document_id,
            num_chunks=result["num_chunks"],
        )

        # 4. Store chunk texts in Redis for BM25 hybrid search
        if settings.BM25_ENABLED:
            try:
                redis: ArqRedis = ctx["redis"]
                bm25_key = f"bm25:doc:{document_id}"
                chunk_records = [
                    {
                        "id": c["id"],
                        "text": c["text"],
                        "metadata": c.get("metadata", {}),
                    }
                    for c in result["chunks"]
                ]
                await redis.set(bm25_key, json.dumps(chunk_records))
                await redis.sadd("bm25:doc_keys", bm25_key)
                await redis.incr("bm25:version")
                logger_adapter.info("BM25 corpus updated", document_id=document_id)
            except Exception as e:
                logger_adapter.warning(f"BM25 Redis store failed (non-fatal): {e}")

        # 5. Mark completed
        repo.update_status(doc_uuid, "completed", num_chunks=result["num_chunks"])
        logger_adapter.info("Ingestion job completed", document_id=document_id)

    except Exception as exc:
        logger_adapter.error("Ingestion job failed", document_id=document_id, error=str(exc))
        repo.update_status(doc_uuid, "failed", error_message=str(exc))
        if isinstance(exc, ValidationError):
            # Permanent failure (bad input, e.g. corrupt/oversized/unsupported file) —
            # retrying can't succeed, so don't burn ARQ retries on it.
            return
        raise  # transient/unknown failure — let ARQ retry
    finally:
        db.close()


async def startup(ctx: Dict[str, Any]) -> None:
    """Initialise shared resources once per worker process."""
    ctx["minio"] = MinioService()
    ctx["ingestion_svc"] = DocumentIngestionService()
    await vector_store.initialize()
    logger_adapter.info("Ingestion worker started")


async def shutdown(ctx: Dict[str, Any]) -> None:
    logger_adapter.info("Ingestion worker shutting down")


class WorkerSettings:
    functions = [process_ingestion]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 10
    job_timeout = 600      # 10 minutes max per document
    keep_result = 3600     # Keep job result in Redis for 1 hour


async def enqueue_ingestion(
    document_id: str,
    storage_key: str,
    file_type: str,
    metadata: Dict[str, Any],
) -> None:
    """
    Enqueue a document ingestion job.
    Called from the upload endpoint after a successful MinIO upload.
    """
    
    redis: ArqRedis = await create_pool(WorkerSettings.redis_settings)
    await redis.enqueue_job(
        "process_ingestion",
        document_id=document_id,
        storage_key=storage_key,
        file_type=file_type,
        metadata=metadata,
    )
    logger_adapter.info(
        "Document process ingestion started",
        document_id=str(document_id),
        )
    await redis.aclose()
