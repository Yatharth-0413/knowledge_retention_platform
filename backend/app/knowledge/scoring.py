"""Knowledge evidence scoring (README section 6).

This measures documented knowledge evidence found in the platform, not a
person's actual competence. Score = topic relevance + content depth +
document count + freshness, kept deliberately simple and explainable.
"""

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.documents.models import Document, DocumentChunk, DocumentStatus
from app.knowledge.models import DocumentTopic, KnowledgeEvidence

_RELEVANCE_WEIGHT = 0.4
_DOC_COUNT_WEIGHT = 0.3
_DEPTH_WEIGHT = 0.2
_FRESHNESS_WEIGHT = 0.1

_DOC_COUNT_CAP = 5
_DEPTH_CHUNK_CAP = 30


def _freshness_score(most_recent: datetime) -> float:
    if most_recent.tzinfo is None:
        most_recent = most_recent.replace(tzinfo=timezone.utc)
    days_since = (datetime.now(timezone.utc) - most_recent).days
    if days_since <= 30:
        return 100.0
    if days_since <= 90:
        return 60.0
    return 30.0


def recompute_evidence(db: Session, user_id: int, topic_id: int) -> KnowledgeEvidence | None:
    rows = (
        db.query(Document, DocumentTopic.relevance)
        .join(DocumentTopic, DocumentTopic.document_id == Document.id)
        .filter(
            Document.uploaded_by_id == user_id,
            DocumentTopic.topic_id == topic_id,
            Document.status == DocumentStatus.READY,
        )
        .all()
    )
    if not rows:
        db.query(KnowledgeEvidence).filter(
            KnowledgeEvidence.user_id == user_id, KnowledgeEvidence.topic_id == topic_id
        ).delete()
        return None

    documents = [doc for doc, _ in rows]
    relevances = [rel for _, rel in rows]
    document_ids = [doc.id for doc in documents]

    avg_relevance = sum(relevances) / len(relevances)
    document_count = len(documents)
    depth = db.query(func.count(DocumentChunk.id)).filter(DocumentChunk.document_id.in_(document_ids)).scalar() or 0
    most_recent = max(doc.created_at for doc in documents)

    score = (
        min(avg_relevance, 1.0) * 100 * _RELEVANCE_WEIGHT
        + min(document_count, _DOC_COUNT_CAP) / _DOC_COUNT_CAP * 100 * _DOC_COUNT_WEIGHT
        + min(depth, _DEPTH_CHUNK_CAP) / _DEPTH_CHUNK_CAP * 100 * _DEPTH_WEIGHT
        + _freshness_score(most_recent) * _FRESHNESS_WEIGHT
    )
    score = round(max(0.0, min(100.0, score)), 1)

    evidence = (
        db.query(KnowledgeEvidence)
        .filter(KnowledgeEvidence.user_id == user_id, KnowledgeEvidence.topic_id == topic_id)
        .first()
    )
    if evidence is None:
        evidence = KnowledgeEvidence(user_id=user_id, topic_id=topic_id, score=score, document_count=document_count)
        db.add(evidence)
    else:
        evidence.score = score
        evidence.document_count = document_count

    return evidence


def recompute_evidence_for_document(db: Session, document: Document) -> None:
    topic_ids = [dt.topic_id for dt in db.query(DocumentTopic).filter(DocumentTopic.document_id == document.id).all()]
    for topic_id in topic_ids:
        recompute_evidence(db, document.uploaded_by_id, topic_id)
