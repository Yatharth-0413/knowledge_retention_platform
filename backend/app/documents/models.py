import enum
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

EMBEDDING_DIM = 384  # sentence-transformers/all-MiniLM-L6-v2


class DocumentStatus(str, enum.Enum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class DocumentType(str, enum.Enum):
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    CSV = "csv"
    EMAIL = "email"  # parsed .msg / .eml; attachments get their own document rows


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType, name="document_type"))
    file_path: Mapped[str] = mapped_column(String(1024))
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status"), default=DocumentStatus.PROCESSING
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set on attachment documents; points at the email document they came from.
    parent_document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    team: Mapped["Team"] = relationship("Team")
    uploaded_by: Mapped["User"] = relationship("User")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan", order_by="DocumentChunk.chunk_index"
    )

    @property
    def uploaded_by_name(self) -> str:
        # For emails this is the credited sender, not necessarily the uploader - see email_parser.py.
        return self.uploaded_by.name


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
