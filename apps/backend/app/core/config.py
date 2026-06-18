from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional, Tuple
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings with environment-specific configurations"""

    # ==================== Environment ====================
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # ==================== API Configuration ====================
    API_V1_PREFIX: str = "/api"
    PROJECT_NAME: str = "RAG Chatbot"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Advanced RAG system with hybrid retrieval and reranking"

    # ==================== Server ====================
    HOST: str = "0.0.0.0"
    PORT: int = 8003
    WORKERS: int = 1

    # ==================== CORS ====================
    CORS_ORIGIN: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]

    CORS_ALLOW_CREDENTITALS: bool = True
    CORS_ALLOW_METHOD: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # ==================== Security ====================
    SECRET_KEY: str
    ALGORITHM: str  = "HS256"
    ACCESS_TOKEN_EXPIRE_MIN: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60

    # API Keys (for API key authentication)
    API_KEY_HEADER: str = "X-API-Key"
    API_KEY_ENABLED: bool = False

    # ==================== Database ====================
    DATABASE_URL: str = "postgresql://rag_user:rag_password@localhost:5432/rag_db"
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_ECHO: bool = False  # SQL query logging
    
    # ==================== Redis ====================
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_DB: int = 0
    REDIS_TTL: int = 3600  # Default cache TTL in seconds
    REDIS_MAX_CONNECTIONS: int = 10
    
    # Semantic Cache Settings
    SEMANTIC_CACHE_ENABLED: bool = True
    SEMANTIC_CACHE_THRESHOLD: float = 0.95  # Similarity threshold
    SEMANTIC_CACHE_TTL: int = 7200  # 2 hours

    # ==================== Vector Database (Qdrant) ====================
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION: str = "documents"
    QDRANT_VECTOR_SIZE: int = 3072  # gemini-embedding-2 dimension

    # ==================== LLM Configuration ====================
    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-large"
    OPENAI_TEMPERATURE: float = 0.7
    OPENAI_MAX_TOKENS: int = 2000
    OPENAI_TIMEOUT: int = 60  # Request timeout in seconds
    
    # Anthropic (optional)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-sonnet-20240229"
    
    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-2"
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Cohere (optional - for reranking)
    COHERE_API_KEY: str = ""
    COHERE_RERANK_MODEL: str = "rerank-english-v3.0"
    
    # ==================== RAG Configuration ====================
    # Document Processing
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    MAX_DOCUMENT_SIZE: int = 10 * 1024 * 1024  # 10 MB
    ALLOWED_FILE_TYPES: List[str] = [".pdf", ".txt", ".md", ".docx", ".csv", ".xlsx"]
    MAX_PDF_PAGES: int = 500       # Reject PDFs larger than this to prevent OOM
    MAX_CHUNKS: int = 5000         # Reject documents that produce too many chunks
    
    # Retrieval
    TOP_K_RETRIEVAL: int = 5
    TOP_K_RERANK: int = 5
    USE_RERANKER: bool = True
    MAX_RERANK_CANDIDATES: int = 15  # fetch this many from Qdrant, rerank down to TOP_K_RERANK
    SIMILARITY_THRESHOLD: float = 0.55
    QUERY_REWRITE_ENABLED: bool = True
    BM25_ENABLED: bool = True
    CONTEXTUAL_ENRICHMENT_ENABLED: bool = False  # requires re-ingestion when enabled
    
    # Hybrid Search
    DENSE_WEIGHT: float = 0.7  # Weight for dense (vector) search
    SPARSE_WEIGHT: float = 0.3  # Weight for sparse (keyword) search
    
    # Query Processing
    MAX_QUERY_LENGTH: int = 500
    MIN_QUERY_LENGTH: int = 3
    
    # ==================== Monitoring & Observability ====================
    ENABLE_METRICS: bool = True
    ENABLE_TRACING: bool = False
    METRICS_PORT: int = 9090

     # Logging
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_FORMAT: str = "json"  # json or text
    
    # ==================== File Storage ====================
    # MinIO/S3 (optional)
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "rag-documents"
    MINIO_SECURE: bool = False
    
    # Local storage fallback
    UPLOAD_DIR: str = "./uploads"
    
    # ==================== Feature Flags ====================
    FEATURE_STREAMING: bool = True
    FEATURE_MEMORY: bool = True
    FEATURE_MULTIMODAL: bool = False
    FEATURE_AGENTIC: bool = False
    
    # ==================== Performance ====================
    # Connection pools
    HTTP_POOL_SIZE: int = 10
    HTTP_TIMEOUT: int = 30
    
    # Async settings
    MAX_CONCURRENT_REQUESTS: int = 100
    REQUEST_TIMEOUT: int = 120  # seconds

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    
    Returns:
        Settings instance
    """
    return Settings()

# Global settings instance
settings = get_settings()
