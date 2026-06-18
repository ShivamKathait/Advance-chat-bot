from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.vector_service import vector_store

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def health_check(db: Session = Depends(get_db)):
    """
    Dependency health check. Returns 200 when all services are reachable,
    503 when any critical dependency is unavailable.
    """
    checks: dict = {}
    overall = "healthy"

    # Qdrant
    try:
        info = await vector_store.get_stats()
        checks["qdrant"] = {"status": "ok", "points": info.get("points_count", 0)}
    except Exception as e:
        checks["qdrant"] = {"status": "error", "detail": str(e)}
        overall = "degraded"

    # Redis
    try:
        r = await vector_store._get_redis()
        await r.ping()
        checks["redis"] = {"status": "ok"}
    except Exception as e:
        checks["redis"] = {"status": "error", "detail": str(e)}
        overall = "degraded"

    # PostgreSQL
    try:
        db.execute(text("SELECT 1"))
        checks["postgres"] = {"status": "ok"}
    except Exception as e:
        checks["postgres"] = {"status": "error", "detail": str(e)}
        overall = "degraded"

    status_code = 200 if overall == "healthy" else 503
    return JSONResponse(
        content={"status": overall, "dependencies": checks},
        status_code=status_code,
    )
