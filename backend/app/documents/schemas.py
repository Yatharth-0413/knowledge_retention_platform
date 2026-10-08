from datetime import datetime

from pydantic import BaseModel

from app.documents.models import DocumentStatus, DocumentType


class DocumentOut(BaseModel):
    id: int
    team_id: int
    uploaded_by_id: int
    uploaded_by_name: str
    filename: str
    file_type: DocumentType
    status: DocumentStatus
    error_message: str | None = None
    parent_document_id: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentChunkOut(BaseModel):
    id: int
    chunk_index: int
    content: str

    model_config = {"from_attributes": True}


class DocumentDetailOut(DocumentOut):
    chunks: list[DocumentChunkOut] = []


class EmailAttachmentOut(BaseModel):
    filename: str
    status: str  # "processed" | "failed" | "skipped"
    document_id: int | None = None
    detail: str | None = None


class EmailIngestOut(BaseModel):
    document: DocumentOut
    subject: str
    sender_email: str
    sender_name: str
    body_chunk_count: int
    attachments_processed: list[EmailAttachmentOut] = []
    attachments_skipped: list[EmailAttachmentOut] = []
