
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document
# Imported for its side effect: registers User with Base's mapper registry so
# Document's string-based relationship("User", ...) can resolve at mapper
# configuration time.
from app.models import user as _user  # noqa: F401


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        id: uuid.UUID,
        filename: str,
        file_type: str,
        storage_key: str,
        content_hash: str | None = None,
        status: str = "pending",
    ) -> Document:
        document = Document(
            id=id,
            file_name=filename,
            file_type=file_type,
            storage_key=storage_key,
            content_hash=content_hash,
            status=status,
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        return self.db.get(Document, document_id)

    def get_by_content_hash(self, content_hash: str) -> Document | None:
        return (
            self.db.execute(
                select(Document)
                .where(Document.content_hash == content_hash, Document.status == "completed")
                .order_by(Document.created_at.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )

    def delete_by_id(self, document_id: uuid.UUID) -> bool:
        document = self.get_by_id(document_id)
        if document:
            self.db.delete(document)
            self.db.commit()
            return True
        return False
        
    def list(self, skip: int = 0, limit: int = 20) -> tuple[list[Document], int]:
        total = self.db.scalar(select(func.count()).select_from(Document)) or 0
        documents = (
            self.db.execute(
                select(Document).order_by(Document.created_at.desc()).offset(skip).limit(limit)
            )
            .scalars()
            .all()
        )
        return list(documents), total

    def update_status(
        self,
        document_id: uuid.UUID,
        status: str,
        num_chunks: int | None = None,
        error_message: str | None = None,
    ) -> Document | None:
        document = self.get_by_id(document_id)
        if document is None:
            return None
        document.status = status
        if num_chunks is not None:
            document.num_chunks = num_chunks
        if error_message is not None:
            document.error_message = error_message[:1024]
        self.db.commit()
        self.db.refresh(document)
        return document