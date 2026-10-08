from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.documents.models import Document
from app.knowledge.models import DocumentTopic, KnowledgeEvidence, Topic
from app.knowledge.schemas import (
    TopicDetailOut,
    TopicDocumentOut,
    TopicPersonEvidenceOut,
    TopicSummaryOut,
    UserTopicEvidenceOut,
)
from app.teams.access import require_team_access, team_user_ids
from app.users.access import can_view_user_profile
from app.users.models import User

router = APIRouter(tags=["knowledge"])


@router.get("/teams/{team_id}/topics", response_model=list[TopicSummaryOut])
def list_team_topics(
    team_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[TopicSummaryOut]:
    require_team_access(team_id, current_user, db)
    # Distinct evidence SUBJECTS per topic, not distinct uploaders - a document's
    # topics can be credited to someone other than whoever uploaded the file (see
    # knowledge/person_attribution.py). Scoped through Document.team_id (not a
    # bare KnowledgeEvidence.user_id-in-roster filter, which would pull in a
    # person's evidence from every team they're on - KnowledgeEvidence has no
    # team_id of its own).
    subject = func.coalesce(DocumentTopic.subject_user_id, Document.uploaded_by_id)
    rows = (
        db.query(
            Topic.id,
            Topic.name,
            func.count(func.distinct(subject)).label("contributor_count"),
            func.count(func.distinct(Document.id)).label("document_count"),
        )
        .join(DocumentTopic, DocumentTopic.topic_id == Topic.id)
        .join(Document, Document.id == DocumentTopic.document_id)
        .filter(Document.team_id == team_id)
        .group_by(Topic.id, Topic.name)
        .order_by(func.count(func.distinct(Document.id)).desc())
        .all()
    )
    return [
        TopicSummaryOut(id=r.id, name=r.name, contributor_count=r.contributor_count, document_count=r.document_count)
        for r in rows
    ]


@router.get("/teams/{team_id}/topics/{topic_id}", response_model=TopicDetailOut)
def get_team_topic(
    team_id: int, topic_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TopicDetailOut:
    team = require_team_access(team_id, current_user, db)

    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")

    # Guard against a direct/URL-navigated topic_id that isn't actually one of
    # this team's own topics - same leak class as list_team_topics above: a team
    # member's evidence on a globally-shared topic name could otherwise surface
    # here even when it came entirely from a *different* team's documents.
    is_team_topic = (
        db.query(DocumentTopic)
        .join(Document, Document.id == DocumentTopic.document_id)
        .filter(DocumentTopic.topic_id == topic_id, Document.team_id == team_id)
        .first()
        is not None
    )
    if not is_team_topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")

    people_rows = (
        db.query(KnowledgeEvidence, User)
        .join(User, User.id == KnowledgeEvidence.user_id)
        .filter(KnowledgeEvidence.topic_id == topic_id, User.id.in_(team_user_ids(team)))
        .order_by(KnowledgeEvidence.score.desc())
        .all()
    )
    people = [
        TopicPersonEvidenceOut(
            user_id=user.id,
            name=user.name,
            designation=user.designation,
            score=evidence.score,
            document_count=evidence.document_count,
            freshness_label=evidence.freshness_label,
        )
        for evidence, user in people_rows
    ]

    doc_rows = (
        db.query(Document, DocumentTopic.relevance)
        .join(DocumentTopic, DocumentTopic.document_id == Document.id)
        .filter(DocumentTopic.topic_id == topic_id, Document.team_id == team_id)
        .order_by(DocumentTopic.relevance.desc())
        .all()
    )
    documents = [
        TopicDocumentOut(id=doc.id, filename=doc.filename, uploaded_by_id=doc.uploaded_by_id, relevance=relevance)
        for doc, relevance in doc_rows
    ]

    return TopicDetailOut(id=topic.id, name=topic.name, people=people, documents=documents)


@router.get("/users/{user_id}/knowledge", response_model=list[UserTopicEvidenceOut])
def get_user_knowledge(
    user_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[UserTopicEvidenceOut]:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not can_view_user_profile(current_user, target):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this profile")

    rows = (
        db.query(KnowledgeEvidence, Topic)
        .join(Topic, Topic.id == KnowledgeEvidence.topic_id)
        .filter(KnowledgeEvidence.user_id == user_id)
        .order_by(KnowledgeEvidence.score.desc())
        .all()
    )
    return [
        UserTopicEvidenceOut(
            topic_id=topic.id,
            topic_name=topic.name,
            score=evidence.score,
            document_count=evidence.document_count,
            freshness_label=evidence.freshness_label,
        )
        for evidence, topic in rows
    ]
