"""Interactive knowledge graph (README section 8): Person -> Topic -> Document.

Edge weight is the knowledge evidence score (0-1) for person->topic edges, and
the extracted relevance (0-1) for topic->document edges, so the frontend can
size/fade edges by strength without a second round trip.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.documents.models import Document, DocumentStatus
from app.graph.schemas import GraphEdgeOut, GraphNodeOut, TeamGraphOut
from app.knowledge.models import DocumentTopic, KnowledgeEvidence, Topic
from app.teams.access import require_team_access, team_user_ids
from app.users.models import User

router = APIRouter(tags=["graph"])


@router.get("/teams/{team_id}/graph", response_model=TeamGraphOut)
def get_team_graph(
    team_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TeamGraphOut:
    team = require_team_access(team_id, current_user, db)
    user_ids = team_user_ids(team)

    users = db.query(User).filter(User.id.in_(user_ids)).all()
    documents = (
        db.query(Document).filter(Document.team_id == team_id, Document.status == DocumentStatus.READY).all()
    )
    document_ids = [d.id for d in documents]

    evidence_rows = (
        db.query(KnowledgeEvidence, Topic)
        .join(Topic, Topic.id == KnowledgeEvidence.topic_id)
        .filter(KnowledgeEvidence.user_id.in_(user_ids))
        .all()
    )
    doc_topic_rows = (
        db.query(DocumentTopic, Topic)
        .join(Topic, Topic.id == DocumentTopic.topic_id)
        .filter(DocumentTopic.document_id.in_(document_ids))
        .all()
        if document_ids
        else []
    )

    topic_by_id = {topic.id: topic for _, topic in evidence_rows}
    topic_by_id.update({topic.id: topic for _, topic in doc_topic_rows})

    nodes = [
        GraphNodeOut(id=f"person-{user.id}", type="person", label=user.name, subtitle=user.designation)
        for user in users
    ]
    nodes += [GraphNodeOut(id=f"topic-{topic.id}", type="topic", label=topic.name) for topic in topic_by_id.values()]
    nodes += [
        GraphNodeOut(id=f"document-{doc.id}", type="document", label=doc.filename, subtitle=doc.file_type.value.upper())
        for doc in documents
    ]

    edges = [
        GraphEdgeOut(source=f"person-{evidence.user_id}", target=f"topic-{topic.id}", weight=round(evidence.score / 100, 3))
        for evidence, topic in evidence_rows
    ]
    edges += [
        GraphEdgeOut(source=f"topic-{topic.id}", target=f"document-{dt.document_id}", weight=round(dt.relevance, 3))
        for dt, topic in doc_topic_rows
    ]

    return TeamGraphOut(nodes=nodes, edges=edges)
