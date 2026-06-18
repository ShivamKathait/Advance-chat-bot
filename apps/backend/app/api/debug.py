from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from arq.connections import create_pool, RedisSettings

from app.core.config import settings
from app.db.session import get_db
from app.repositories.document_repository import DocumentRepository
from app.services.vector_service import vector_store

router = APIRouter(prefix="/api/v1/debug", tags=["Debug"])


@router.get("/status")
async def pipeline_status(db: Session = Depends(get_db)):
    """
    Returns a snapshot of the full pipeline state:
    - Qdrant collection existence and point count
    - Redis ARQ queue pending job count
    - Last 10 documents with their ingestion status
    """
    # Qdrant
    try:
        info = await vector_store.get_stats()
        qdrant_info = {"collection": settings.QDRANT_COLLECTION, "exists": True, **info}
    except Exception as e:
        qdrant_info = {"collection": settings.QDRANT_COLLECTION, "exists": False, "error": str(e)}

    # Redis / ARQ queue
    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        pending = await redis.zcard("arq:queue")
        await redis.aclose()
        redis_info = {"connected": True, "pending_jobs": pending}
    except Exception as e:
        redis_info = {"connected": False, "error": str(e)}

    # Recent documents from DB
    repo = DocumentRepository(db)
    docs, total = repo.list(limit=10)
    recent_documents = [
        {
            "id": str(d.id),
            "filename": d.file_name,
            "status": d.status,
            "num_chunks": d.num_chunks,
            "error_message": d.error_message,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]

    return {
        "qdrant": qdrant_info,
        "redis": redis_info,
        "recent_documents": recent_documents,
        "total_documents": total,
    }


@router.get("/rag-stats")
async def rag_pipeline_stats():
    """
    Returns aggregate latency and quality stats from the last 100 RAG pipeline runs.
    Useful for measuring the impact of config changes (threshold, top_k, reranker on/off).
    """
    return vector_store.get_pipeline_stats()
