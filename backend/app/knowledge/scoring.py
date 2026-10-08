"""Knowledge evidence scoring (README section 6).

This measures documented knowledge evidence found in the platform, not a
person's actual competence. Score = topic relevance + content depth +
document count + freshness, kept deliberately simple and explainable.
"""

from datetime import datetime, timezone

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.documents.models import Document, DocumentChunk, DocumentStatus
from app.knowledge.models import DocumentTopic, KnowledgeEvidence

_RELEVANCE_WEIGHT = 0.4
_DOC_COUNT_WEIGHT = 0.3
_DEPTH_WEIGHT = 0.2
_FRESHNESS_WEIGHT = 0.1

_DOC_COUNT_CAP = 5
_DEPTH_CHUNK_CAP = 30


def _days_since(most_recent: datetime) -> int:
    if most_recent.tzinfo is None:
        most_recent = most_recent.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - most_recent).days


def _freshness_score(most_recent: datetime) -> float:
    days_since = _days_since(most_recent)
    if days_since <= 30:
        return 100.0
    if days_since <= 90:
        return 60.0
    return 30.0


def _freshness_label(most_recent: datetime) -> str:
    """Labeled bucket for display - kept distinct from `score` (the 0-100
    "knowledge level") so the UI never conflates "how much evidence" with "how
    recently it was updated" (issue doc section 14)."""
    days_since = _days_since(most_recent)
    if days_since <= 30:
        return "New"
    if days_since <= 90:
        return "Medium"
    return "Old"


def recompute_evidence(db: Session, user_id: int, topic_id: int) -> KnowledgeEvidence | None:
    """Recompute (user_id, topic_id) evidence from every DocumentTopic link that
    belongs to this user - either explicitly (subject_user_id == user_id, set when
    a structured document's row was identified as being about them, see
    person_attribution.py) or implicitly (subject_user_id is NULL and they
    uploaded the document - the original, still-default behavior for ordinary
    documents).
    """
    rows = (
        db.query(Document, DocumentTopic.relevance)
        .join(DocumentTopic, DocumentTopic.document_id == Document.id)
        .filter(
            DocumentTopic.topic_id == topic_id,
            Document.status == DocumentStatus.READY,
            or_(
                DocumentTopic.subject_user_id == user_id,
                and_(DocumentTopic.subject_user_id.is_(None), Document.uploaded_by_id == user_id),
            ),
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
    freshness_label = _freshness_label(most_recent)

    evidence = (
        db.query(KnowledgeEvidence)
        .filter(KnowledgeEvidence.user_id == user_id, KnowledgeEvidence.topic_id == topic_id)
        .first()
    )
    if evidence is None:
        evidence = KnowledgeEvidence(
            user_id=user_id,
            topic_id=topic_id,
            score=score,
            document_count=document_count,
            freshness_label=freshness_label,
        )
        db.add(evidence)
    else:
        evidence.score = score
        evidence.document_count = document_count
        evidence.freshness_label = freshness_label

    return evidence
