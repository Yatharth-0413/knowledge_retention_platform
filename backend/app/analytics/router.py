from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.analytics.schemas import (
    ContributionActivityOut,
    CoverageBuckets,
    DependencyContributor,
    DependencyTopicOut,
    DocumentTypeCount,
    FreshnessBreakdown,
    KnowledgeByMemberItem,
    KnowledgeByTopicItem,
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
    # "Active contributor" / per-topic coverage must count distinct EVIDENCE
    # SUBJECTS, not distinct uploaders - a document's topics can be credited to
    # someone other than whoever uploaded the file (e.g. a roster spreadsheet
    # uploaded by a manager; see knowledge/person_attribution.py). Scoped through
    # Document.team_id (not a bare KnowledgeEvidence.user_id-in-roster filter,
    # which would pull in a person's evidence from every team they're on, not
    # just this one - KnowledgeEvidence has no team_id of its own).
    subject = func.coalesce(DocumentTopic.subject_user_id, Document.uploaded_by_id)
    active_contributor_count = (
        db.query(func.count(func.distinct(subject)))
        .join(Document, Document.id == DocumentTopic.document_id)
        .filter(Document.team_id == team_id)
        .scalar()
        or 0
    )

    contributor_counts = (
        db.query(Topic.id, func.count(func.distinct(subject)).label("contributors"))
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

    # Same team_topic_ids/roster scoping as get_dependency_analysis below - KnowledgeEvidence
    # is global per (user, topic), not team-scoped, so these chart aggregates must go through
    # this team's own DocumentTopic rows rather than a bare roster-membership filter.
    team_topic_ids = (
        db.query(DocumentTopic.topic_id)
        .join(Document, Document.id == DocumentTopic.document_id)
        .filter(Document.team_id == team_id)
        .distinct()
    )
    roster_ids = team_user_ids(team)

    member_rows = (
        db.query(User.id, User.name, func.avg(KnowledgeEvidence.score))
        .join(KnowledgeEvidence, KnowledgeEvidence.user_id == User.id)
        .filter(User.id.in_(roster_ids), KnowledgeEvidence.topic_id.in_(team_topic_ids))
        .group_by(User.id, User.name)
        .all()
    )
    knowledge_by_member = [
        KnowledgeByMemberItem(user_id=uid, name=name, avg_score=round(avg_score or 0.0, 1))
        for uid, name, avg_score in member_rows
    ]

    topic_rows = (
        db.query(Topic.id, Topic.name, func.avg(KnowledgeEvidence.score))
        .join(KnowledgeEvidence, KnowledgeEvidence.topic_id == Topic.id)
        .filter(KnowledgeEvidence.topic_id.in_(team_topic_ids), KnowledgeEvidence.user_id.in_(roster_ids))
        .group_by(Topic.id, Topic.name)
        .all()
    )
    knowledge_by_topic = [
        KnowledgeByTopicItem(topic_id=tid, topic_name=name, avg_score=round(avg_score or 0.0, 1))
        for tid, name, avg_score in topic_rows
    ]

    freshness_counts = dict(
        db.query(KnowledgeEvidence.freshness_label, func.count(KnowledgeEvidence.id))
        .filter(KnowledgeEvidence.topic_id.in_(team_topic_ids), KnowledgeEvidence.user_id.in_(roster_ids))
        .group_by(KnowledgeEvidence.freshness_label)
        .all()
    )
    freshness_breakdown = FreshnessBreakdown(
        new=freshness_counts.get("New", 0),
        medium=freshness_counts.get("Medium", 0),
        old=freshness_counts.get("Old", 0),
    )

    documents_by_type = [
        DocumentTypeCount(file_type=file_type.value, count=count)
        for file_type, count in (
            db.query(Document.file_type, func.count(Document.id))
            .filter(Document.team_id == team_id)
            .group_by(Document.file_type)
            .all()
        )
    ]

    return TeamDashboardOut(
        member_count=len(team.members),
        document_count=document_count,
        topic_count=len(contributor_counts),
        active_contributor_count=active_contributor_count,
        coverage=coverage,
        recent_activity=recent_activity,
        knowledge_by_member=knowledge_by_member,
        knowledge_by_topic=knowledge_by_topic,
        freshness_breakdown=freshness_breakdown,
        documents_by_type=documents_by_type,
    )


@router.get("/teams/{team_id}/dependency", response_model=list[DependencyTopicOut])
def get_dependency_analysis(
    team_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[DependencyTopicOut]:
    team = require_team_access(team_id, current_user, db)

    # Scope to topics this team's own documents actually produced - filtering by
    # team membership alone (as this used to) leaks a topic into every team a
    # person belongs to, even a team with zero documents on it, whenever that
    # person has KnowledgeEvidence on the same (globally-deduplicated) topic from
    # a *different* team (e.g. a manager who manages more than one team).
    team_topic_ids = (
        db.query(DocumentTopic.topic_id)
        .join(Document, Document.id == DocumentTopic.document_id)
        .filter(Document.team_id == team_id)
        .distinct()
    )
    rows = (
        db.query(Topic, KnowledgeEvidence, User)
        .join(KnowledgeEvidence, KnowledgeEvidence.topic_id == Topic.id)
        .join(User, User.id == KnowledgeEvidence.user_id)
        .filter(KnowledgeEvidence.topic_id.in_(team_topic_ids), User.id.in_(team_user_ids(team)))
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

    # Derived straight from this team's own DocumentTopic/Document rows (subject
    # attribution, falling back to uploader - see knowledge/person_attribution.py)
    # rather than the global KnowledgeEvidence table, which has no team scoping
    # and would otherwise count a person's topics from every team they're on.
    subject = func.coalesce(DocumentTopic.subject_user_id, Document.uploaded_by_id)
    topic_counts = dict(
        db.query(subject, func.count(func.distinct(DocumentTopic.topic_id)))
        .join(Document, Document.id == DocumentTopic.document_id)
        .filter(Document.team_id == team_id)
        .group_by(subject)
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
