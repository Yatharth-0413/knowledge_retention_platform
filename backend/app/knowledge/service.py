"""Glue between document processing and the knowledge module: link extracted
topics to a document and refresh the affected evidence scores."""

from sqlalchemy.orm import Session

from app.documents.models import Document, DocumentChunk
from app.knowledge.embeddings import embed_query, embed_texts
from app.knowledge.models import DocumentTopic, Topic
from app.knowledge.scoring import recompute_evidence
from app.knowledge.topic_extraction import extract_topics, normalize_topic_name

_MIN_RELEVANCE = 0.4
_RELEVANCE_STEP = 0.08

# Cosine similarity above which a newly-extracted topic name is considered the same
# concept as an existing topic and reused rather than creating a near-duplicate
# (e.g. "Deployment Approval" / "DevOps Deployment" -> "Deployment"). Tuned to stay
# below the similarity of genuinely distinct-but-related concepts like "Java" vs
# "JavaScript" - verify that pair specifically if this is ever retuned.
_TOPIC_SIMILARITY_THRESHOLD = 0.82


def _get_or_create_topic(db: Session, name: str) -> Topic:
    normalized = normalize_topic_name(name)
    topic = db.query(Topic).filter(Topic.normalized_name == normalized).first()
    if topic is not None:
        return topic

    embedding = embed_query(name)
    reused = _find_similar_topic(db, embedding)
    if reused is not None:
        return reused

    topic = Topic(name=name.strip(), normalized_name=normalized, embedding=embedding)
    db.add(topic)
    db.flush()
    return topic


def _find_similar_topic(db: Session, embedding: list[float]) -> Topic | None:
    """Reuse an existing topic whose name embedding is close enough to count as the
    same concept, instead of creating a near-duplicate. See _TOPIC_SIMILARITY_THRESHOLD.
    """
    distance = Topic.embedding.cosine_distance(embedding)
    closest = (
        db.query(Topic, distance.label("distance"))
        .filter(Topic.embedding.isnot(None))
        .order_by(distance)
        .first()
    )
    if closest is None:
        return None
    topic, topic_distance = closest
    if (1 - topic_distance) >= _TOPIC_SIMILARITY_THRESHOLD:
        return topic
    return None


def process_document_topics(db: Session, document: Document, text: str, subject_user_id: int | None = None) -> list[int]:
    """Extract topics from `text` and link them to `document`, crediting the
    resulting evidence to `subject_user_id` if given, else the document's
    uploader (the original, default behavior for ordinary documents - see
    DocumentTopic.subject_user_id).

    Returns the linked topic ids. Recomputes evidence only for the (owner, topic)
    pairs just touched by this call, so this is safe to call more than once per
    document (e.g. once per person-row in a roster spreadsheet, see
    person_attribution.py) without one call's recompute stomping another's.
    """
    owner_id = subject_user_id if subject_user_id is not None else document.uploaded_by_id
    topic_names = extract_topics(text)
    seen_topic_ids: set[int] = set()
    topic_ids: list[int] = []
    for index, name in enumerate(topic_names):
        topic = _get_or_create_topic(db, name)
        if topic.id in seen_topic_ids:
            # extract_topics() can return near-duplicate phrases (e.g. "Software"
            # and "Software Development") that _find_similar_topic resolves to
            # the same existing Topic - skip the repeat rather than violate
            # uq_document_topic_subject with a second insert for the same
            # (document, topic, subject).
            continue
        seen_topic_ids.add(topic.id)
        relevance = max(_MIN_RELEVANCE, 1.0 - index * _RELEVANCE_STEP)
        db.add(DocumentTopic(document_id=document.id, topic_id=topic.id, relevance=relevance, subject_user_id=subject_user_id))
        topic_ids.append(topic.id)

    db.flush()
    for topic_id in topic_ids:
        recompute_evidence(db, owner_id, topic_id)
    return topic_ids


def embed_document_chunks(chunks: list[DocumentChunk]) -> None:
    """Compute and assign embeddings in place; caller is responsible for flush/commit."""
    if not chunks:
        return
    vectors = embed_texts([chunk.content for chunk in chunks])
    for chunk, vector in zip(chunks, vectors):
        chunk.embedding = vector
