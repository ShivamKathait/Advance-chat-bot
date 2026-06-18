import uuid
import uvicorn

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import setup_logging, logger_adapter
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.debug import router as debug_router
from app.api.health import router as health_router
from app.db.base import Base
from app.db.session import engine
import app.models.conversation  # noqa: F401 — registers Conversation + Message with Base.metadata
import app.models.document      # noqa: F401 — registers Document with Base.metadata
import app.models.feedback      # noqa: F401 — registers Feedback with Base.metadata
from app.services.vector_service import vector_store

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    Base.metadata.create_all(bind=engine)
    try:
        await vector_store.initialize()
        logger_adapter.info("Qdrant collection ready")
    except Exception as e:
        logger_adapter.error(f"Qdrant init failed: {e}")
    logger_adapter.info("RAG Chatbot API starting", environment=settings.ENVIRONMENT)
    yield
    logger_adapter.info("RAG Chatbot API shutting down")


app = FastAPI(
    title = settings.PROJECT_NAME,
    description = settings.DESCRIPTION,
    version = settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)
 

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins = settings.CORS_ORIGIN,
    allow_credentials = settings.CORS_ALLOW_CREDENTITALS,
    allow_methods = settings.CORS_ALLOW_METHOD,
    allow_headers = settings.CORS_ALLOW_HEADERS,
)

from prometheus_client import make_asgi_app
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(debug_router)


@app.get("/")
async def root():
    return {
        "name": "RAG Chatbot API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }
 
 
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host = settings.HOST,
        port = settings.PORT,
        reload = True
    )