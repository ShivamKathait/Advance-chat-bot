from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.auth_repository import AuthRepository
from app.repositories.chat_repository import ChatRepository
from app.repositories.document_repository import DocumentRepository
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
from app.services.document_service import DocumentService
from app.services.minio_service import MinioService
from app.services.vector_service import vector_store


def get_minio_service():
    return MinioService()

def get_document_repository(db: Session = Depends(get_db)) -> DocumentRepository:
    return DocumentRepository(db)

def get_document_service(
    minio_service: MinioService = Depends(get_minio_service),
    repository: DocumentRepository = Depends(get_document_repository),
):
    return DocumentService(minio_service=minio_service, repository=repository)


def get_chat_repository(db: Session = Depends(get_db)) -> ChatRepository:
    return ChatRepository(db)

def get_chat_service(
    chat_repository: ChatRepository = Depends(get_chat_repository),
) -> ChatService:
    return ChatService(vector_service=vector_store, chat_repository=chat_repository)


def get_auth_repository(db: Session = Depends(get_db)) -> AuthRepository:
    return AuthRepository(db)

def get_auth_service(
    get_auth_repository: AuthRepository = Depends(get_auth_repository),
) -> AuthService:
    return AuthService()
