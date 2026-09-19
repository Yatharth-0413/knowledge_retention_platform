"""Glue between document processing and the knowledge module: link extracted
topics to a document and refresh the uploader's evidence scores."""

from sqlalchemy.orm import Session

from app.documents.models import Document, DocumentChunk
from app.knowledge.embeddings import embed_texts
from app.knowledge.models import DocumentTopic, Topic
from app.knowledge.scoring import recompute_evidence_for_document
from app.knowledge.topic_extraction import extract_topics, normalize_topic_name

_MIN_RELEVANCE = 0.4
_RELEVANCE_STEP = 0.08


def _get_or_create_topic(db: Session, name: str) -> Topic:
    normalized = normalize_topic_name(name)
    topic = db.query(Topic).filter(Topic.normalized_name == normalized).first()
    if topic is None:
        topic = Topic(name=name.strip(), normalized_name=normalized)
        db.add(topic)
        db.flush()
    return topic


def process_document_topics(db: Session, document: Document, text: str) -> None:
    topic_names = extract_topics(text)
    for index, name in enumerate(topic_names):
        topic = _get_or_create_topic(db, name)
        relevance = max(_MIN_RELEVANCE, 1.0 - index * _RELEVANCE_STEP)
        db.add(DocumentTopic(document_id=document.id, topic_id=topic.id, relevance=relevance))

    db.flush()
    recompute_evidence_for_document(db, document)


def embed_document_chunks(chunks: list[DocumentChunk]) -> None:
    """Compute and assign embeddings in place; caller is responsible for flush/commit."""
    if not chunks:
        return
    vectors = embed_texts([chunk.content for chunk in chunks])
    for chunk, vector in zip(chunks, vectors):
        chunk.embedding = vector
