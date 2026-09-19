from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DocumentTopic(Base):
    """A topic detected in a document, with the extractor's confidence."""

    __tablename__ = "document_topics"
    __table_args__ = (UniqueConstraint("document_id", "topic_id", name="uq_document_topic"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), index=True)
    relevance: Mapped[float] = mapped_column(Float, default=1.0)

    document: Mapped["Document"] = relationship("Document")
    topic: Mapped["Topic"] = relationship("Topic")


class KnowledgeEvidence(Base):
    """Cached per-user, per-topic documented-knowledge-evidence score (0-100).

    Recomputed whenever a document contributing to this (user, topic) pair is
    processed; see app.knowledge.scoring. Not a measure of actual skill —
    see the README's framing in section 6.
    """

    __tablename__ = "knowledge_evidence"
    __table_args__ = (UniqueConstraint("user_id", "topic_id", name="uq_user_topic_evidence"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), index=True)

    score: Mapped[float] = mapped_column(Float)
    document_count: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship("User")
    topic: Mapped["Topic"] = relationship("Topic")
