from typing import Literal

from pydantic import BaseModel

from app.recommendations.classification import Category, TopicCategory


class ExistingContributorOut(BaseModel):
    user_id: int
    name: str
    designation: str | None = None
    category: Category
    score: float


class GapCandidateOut(BaseModel):
    user_id: int
    name: str
    designation: str | None = None
    category: Literal["functional", "technical"]


class TopicRecommendationOut(BaseModel):
    topic_id: int
    topic_name: str
    category: TopicCategory
    existing_contributors: list[ExistingContributorOut]
    gap_candidates: list[GapCandidateOut]


class CategorySummaryOut(BaseModel):
    category: Literal["functional", "technical"]
    member_count: int
    topic_count: int
    gap_member_count: int
    gap_pair_count: int


class RecommendationsSummaryOut(BaseModel):
    functional: CategorySummaryOut
    technical: CategorySummaryOut
    unclassified_member_count: int
    unclassified_topic_count: int


class TeamRecommendationsOut(BaseModel):
    team_id: int
    topics: list[TopicRecommendationOut]
    summary: RecommendationsSummaryOut
