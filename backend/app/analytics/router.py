from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.analytics.schemas import (
    ContributionActivityOut,
    CoverageBuckets,
    DependencyContributor,
    DependencyTopicOut,
    RecentActivityItem,
    TeamDashboardOut,
)
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.documents.models import Document
from app.knowledge.models import DocumentTopic, KnowledgeEvidence, Topic
from app.teams.access import require_team_access, team_user_ids
from app.users.models import User

router = APIRouter(tags=["analytics"])

_HIGH_CONCENTRATION_SHARE = 0.6


@router.get("/teams/{team_id}/dashboard", response_model=TeamDashboardOut)
def get_team_dashboard(
    team_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TeamDashboardOut:
    team = require_team_access(team_id, current_user, db)

    document_count = db.query(func.count(Document.id)).filter(Document.team_id == team_id).scalar() or 0
    active_contributor_count = (
        db.query(func.count(func.distinct(Document.uploaded_by_id))).filter(Document.team_id == team_id).scalar()
        or 0
    )

    contributor_counts = (
        db.query(Topic.id, func.count(func.distinct(Document.uploaded_by_id)).label("contributors"))
        .join(DocumentTopic, DocumentTopic.topic_id == Topic.id)
        .join(Document, Document.id == DocumentTopic.document_id)
        .filter(Document.team_id == team_id)
        .group_by(Topic.id)
        .all()
    )
    coverage = CoverageBuckets(well_covered=0, moderately_covered=0, weakly_covered=0)
    for _, contributors in contributor_counts:
        if contributors >= 3:
            coverage.well_covered += 1
        elif contributors == 2:
            coverage.moderately_covered += 1
        else:
            coverage.weakly_covered += 1

    recent_docs = (
        db.query(Document, User.name)
        .join(User, User.id == Document.uploaded_by_id)
        .filter(Document.team_id == team_id)
        .order_by(Document.created_at.desc())
        .limit(5)
        .all()
    )
    recent_activity = [
        RecentActivityItem(user_name=name, filename=doc.filename, created_at=doc.created_at.isoformat())
        for doc, name in recent_docs
    ]

    return TeamDashboardOut(
        member_count=len(team.members),
        document_count=document_count,
        topic_count=len(contributor_counts),
        active_contributor_count=active_contributor_count,
        coverage=coverage,
        recent_activity=recent_activity,
    )


@router.get("/teams/{team_id}/dependency", response_model=list[DependencyTopicOut])
def get_dependency_analysis(
    team_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[DependencyTopicOut]:
    team = require_team_access(team_id, current_user, db)

    rows = (
        db.query(Topic, KnowledgeEvidence, User)
        .join(KnowledgeEvidence, KnowledgeEvidence.topic_id == Topic.id)
        .join(User, User.id == KnowledgeEvidence.user_id)
        .filter(User.id.in_(team_user_ids(team)))
        .order_by(Topic.id, KnowledgeEvidence.score.desc())
        .all()
    )

    by_topic: dict[int, list] = defaultdict(list)
    topic_names: dict[int, str] = {}
    for topic, evidence, user in rows:
        topic_names[topic.id] = topic.name
        by_topic[topic.id].append((user, evidence))

    results = []
    for topic_id, entries in by_topic.items():
        total_score = sum(evidence.score for _, evidence in entries)
        if total_score <= 0:
            continue
        contributors = [
            DependencyContributor(user_id=user.id, name=user.name, share=round(evidence.score / total_score, 3))
            for user, evidence in entries
        ]
        top_share = contributors[0].share if contributors else 0.0
        concentration = "HIGH" if top_share >= _HIGH_CONCENTRATION_SHARE else "DISTRIBUTED"
        results.append(
            DependencyTopicOut(
                topic_id=topic_id, topic_name=topic_names[topic_id], contributors=contributors, concentration=concentration
            )
        )

    results.sort(key=lambda r: r.contributors[0].share if r.contributors else 0, reverse=True)
    return results


@router.get("/teams/{team_id}/contributions", response_model=list[ContributionActivityOut])
def get_contribution_activity(
    team_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ContributionActivityOut]:
    """Knowledge Contribution Activity (README section 16) — documents uploaded and
    topics contributed per person, without treating it as employee performance."""
    team = require_team_access(team_id, current_user, db)
    user_ids = team_user_ids(team)

    doc_rows = (
        db.query(
            User.id,
            User.name,
            func.count(Document.id).label("document_count"),
            func.max(Document.created_at).label("last_activity"),
        )
        .outerjoin(Document, and_(Document.uploaded_by_id == User.id, Document.team_id == team_id))
        .filter(User.id.in_(user_ids))
        .group_by(User.id, User.name)
        .all()
    )

    topic_counts = dict(
        db.query(KnowledgeEvidence.user_id, func.count(func.distinct(KnowledgeEvidence.topic_id)))
        .filter(KnowledgeEvidence.user_id.in_(user_ids))
        .group_by(KnowledgeEvidence.user_id)
        .all()
    )

    items = [
        ContributionActivityOut(
            user_id=user_id,
            name=name,
            document_count=document_count,
            topic_count=topic_counts.get(user_id, 0),
            last_activity=last_activity.isoformat() if last_activity else None,
        )
        for user_id, name, document_count, last_activity in doc_rows
    ]
    items.sort(key=lambda i: i.document_count, reverse=True)
    return items
