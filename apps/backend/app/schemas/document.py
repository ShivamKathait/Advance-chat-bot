from typing import Annotated, List, Optional
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


class DocumentResponse(BaseModel):
    """Response returned immediately after upload."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: Annotated[str, BeforeValidator(str)]
    filename: str = Field(validation_alias="file_name")
    file_type: str
    status: str
    num_chunks: int = 0
    message: str = ""


class DocumentStatusResponse(BaseModel):
    """Lightweight status-poll response."""
    id: str
    status: str
    num_chunks: int = 0
    error_message: Optional[str] = None


class DocumentListResponse(BaseModel):
    """Paginated document list."""
    documents: List[DocumentResponse]
    total: int

class DocumentDeleteResponse(BaseModel):
    status: str
    message: str
    document_id: str