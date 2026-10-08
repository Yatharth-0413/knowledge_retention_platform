from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

_TOPIC_EMBEDDING_DIM = 384  # sentence-transformers/all-MiniLM-L6-v2, same model as document chunks


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # Embedding of `name`, used to reuse a semantically-equivalent existing topic
    # ("Deployment Approval" -> "Deployment") instead of creating a near-duplicate
    # when the exact-normalized-string match misses. See knowledge/service.py.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_TOPIC_EMBEDDING_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DocumentTopic(Base):
    """A topic detected in a document, with the extractor's confidence.

    subject_user_id: who this specific topic's evidence belongs to. NULL (the
    default, and the only value before this column existed) means "the
    document's uploader" - today's behavior for ordinary documents. Set to a
    specific team member when a structured document (e.g. a roster
    spreadsheet) has a row identified as being about that person, so their
    knowledge is credited to them rather than to whoever uploaded the file.
    See knowledge/person_attribution.py.
    """

    __tablename__ = "document_topics"
    __table_args__ = (
        # postgresql_nulls_not_distinct: Postgres normally treats NULL != NULL in a
        # unique constraint, which would let the same (document, topic) pair with
        # subject_user_id=NULL (the ordinary, unattributed case) be inserted more
        # than once. This keeps that case strictly unique while still allowing the
        # same document+topic to appear once per distinct attributed subject.
        UniqueConstraint(
            "document_id", "topic_id", "subject_user_id",
            name="uq_document_topic_subject",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), index=True)
    subject_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
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
    # How recently this evidence was last touched - deliberately kept separate from
    # `score` (the 0-100 "knowledge level"), since a high-scoring topic can still be
    # stale and a freshly-updated one can still be thin. See scoring.py::_freshness_label.
    freshness_label: Mapped[str] = mapped_column(String(10), default="New")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship("User")
    topic: Mapped["Topic"] = relationship("Topic")
