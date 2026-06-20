import uuid
import uvicorn

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import make_asgi_app

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import setup_logging, logger_adapter
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.debug import router as debug_router
from app.api.health import router as health_router
from app.db.base import Base
from app.db.session import engine
from app.schemas.errors import ErrorBody, ErrorResponse
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
        raise
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


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    logger_adapter.warning(
        "Handled application error",
        error_code=exc.error_code,
        error_message=exc.message,
        path=request.url.path,
        request_id=getattr(request.state, "request_id", None),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error=ErrorBody(code=exc.error_code, message=exc.message)).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error=ErrorBody(code="VALIDATION_ERROR", message="Invalid request data")
        ).model_dump(),
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error=ErrorBody(code="HTTP_ERROR", message=str(exc.detail))).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger_adapter.error(
        "Unhandled exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
        request_id=getattr(request.state, "request_id", None),
    )
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=ErrorBody(code="INTERNAL_ERROR", message="An unexpected error occurred")
        ).model_dump(),
    )

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