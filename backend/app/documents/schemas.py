from datetime import datetime

from pydantic import BaseModel

from app.documents.models import DocumentStatus, DocumentType


class DocumentOut(BaseModel):
    id: int
    team_id: int
    uploaded_by_id: int
    filename: str
    file_type: DocumentType
    status: DocumentStatus
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentChunkOut(BaseModel):
    id: int
    chunk_index: int
    content: str

    model_config = {"from_attributes": True}


class DocumentDetailOut(DocumentOut):
    chunks: list[DocumentChunkOut] = []
