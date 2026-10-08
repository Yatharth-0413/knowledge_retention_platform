from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.documents.models import Document, DocumentStatus
from app.knowledge.models import DocumentTopic, KnowledgeEvidence, Topic
from app.recommendations.classification import Category, classify_designation, classify_topic_category
from app.recommendations.schemas import (
    CategorySummaryOut,
    ExistingContributorOut,
    GapCandidateOut,
    RecommendationsSummaryOut,
    TeamRecommendationsOut,
    TopicRecommendationOut,
)
from app.teams.access import require_team_access, team_user_ids
from app.users.models import User

router = APIRouter(tags=["recommendations"])


@router.get("/teams/{team_id}/recommendations", response_model=TeamRecommendationsOut)
def get_team_recommendations(
    team_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TeamRecommendationsOut:
    team = require_team_access(team_id, current_user, db)
    roster_ids = team_user_ids(team)

    roster = db.query(User).filter(User.id.in_(roster_ids)).all()
    category_by_user: dict[int, Category] = {u.id: classify_designation(u.designation) for u in roster}
    user_by_id: dict[int, User] = {u.id: u for u in roster}

    # Same team_topic_ids scoping as analytics/router.py - KnowledgeEvidence has no team_id of
    # its own, so the team's topic set must come from this team's own DocumentTopic/Document rows.
    topic_rows = (
        db.query(DocumentTopic.topic_id, Topic.name)
        .join(Topic, Topic.id == DocumentTopic.topic_id)
        .join(Document, Document.id == DocumentTopic.document_id)
        .filter(Document.team_id == team_id, Document.status == DocumentStatus.READY)
        .distinct()
        .all()
    )
    topic_name_by_id: dict[int, str] = dict(topic_rows)

    evidence_rows = (
        db.query(KnowledgeEvidence.user_id, KnowledgeEvidence.topic_id, KnowledgeEvidence.score)
        .filter(KnowledgeEvidence.topic_id.in_(list(topic_name_by_id.keys())), KnowledgeEvidence.user_id.in_(roster_ids))
        .all()
    )
    evidence_by_topic: dict[int, list[tuple[int, float]]] = {}
    for user_id, topic_id, score in evidence_rows:
        evidence_by_topic.setdefault(topic_id, []).append((user_id, score))

    functional_pool = {uid for uid, cat in category_by_user.items() if cat == "functional"}
    technical_pool = {uid for uid, cat in category_by_user.items() if cat == "technical"}

    topics: list[TopicRecommendationOut] = []

    for topic_id, topic_name in topic_name_by_id.items():
        entries = evidence_by_topic.get(topic_id, [])
        contributor_ids = {uid for uid, _ in entries}
        category = classify_topic_category([category_by_user.get(uid, "unclassified") for uid in contributor_ids])

        existing_contributors = [
            ExistingContributorOut(
                user_id=uid,
                name=user_by_id[uid].name,
                designation=user_by_id[uid].designation,
                category=category_by_user.get(uid, "unclassified"),
                score=score,
            )
            for uid, score in entries
        ]

        if category == "functional":
            gap_ids = functional_pool - contributor_ids
        elif category == "technical":
            gap_ids = technical_pool - contributor_ids
        elif category == "mixed":
            gap_ids = (functional_pool | technical_pool) - contributor_ids
        else:
            gap_ids = set()

        gap_candidates = [
            GapCandidateOut(
                user_id=uid,
                name=user_by_id[uid].name,
                designation=user_by_id[uid].designation,
                category=category_by_user[uid],  # always functional/technical by construction
            )
            for uid in gap_ids
        ]

        topics.append(
            TopicRecommendationOut(
                topic_id=topic_id,
                topic_name=topic_name,
                category=category,
                existing_contributors=existing_contributors,
                gap_candidates=gap_candidates,
            )
        )

    topics.sort(key=lambda t: (-len(t.gap_candidates), t.topic_name))

    def _category_summary(category: Category) -> CategorySummaryOut:
        pool = functional_pool if category == "functional" else technical_pool
        gap_members: set[int] = set()
        gap_pair_count = 0
        topic_count = 0
        for topic in topics:
            if topic.category == category:
                topic_count += 1
            for candidate in topic.gap_candidates:
                if candidate.category == category:
                    gap_members.add(candidate.user_id)
                    gap_pair_count += 1
        return CategorySummaryOut(
            category=category,
            member_count=len(pool),
            topic_count=topic_count,
            gap_member_count=len(gap_members),
            gap_pair_count=gap_pair_count,
        )

    summary = RecommendationsSummaryOut(
        functional=_category_summary("functional"),
        technical=_category_summary("technical"),
        unclassified_member_count=sum(1 for cat in category_by_user.values() if cat == "unclassified"),
        unclassified_topic_count=sum(1 for topic in topics if topic.category == "unclassified"),
    )

    return TeamRecommendationsOut(team_id=team_id, topics=topics, summary=summary)
