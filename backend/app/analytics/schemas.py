from pydantic import BaseModel


class CoverageBuckets(BaseModel):
    well_covered: int
    moderately_covered: int
    weakly_covered: int


class RecentActivityItem(BaseModel):
    user_name: str
    filename: str
    created_at: str


class KnowledgeByMemberItem(BaseModel):
    user_id: int
    name: str
    avg_score: float


class KnowledgeByTopicItem(BaseModel):
    topic_id: int
    topic_name: str
    avg_score: float


class FreshnessBreakdown(BaseModel):
    new: int
    medium: int
    old: int


class DocumentTypeCount(BaseModel):
    file_type: str
    count: int


class TeamDashboardOut(BaseModel):
    member_count: int
    document_count: int
    topic_count: int
    active_contributor_count: int
    coverage: CoverageBuckets
    recent_activity: list[RecentActivityItem]
    knowledge_by_member: list[KnowledgeByMemberItem]
    knowledge_by_topic: list[KnowledgeByTopicItem]
    freshness_breakdown: FreshnessBreakdown
    documents_by_type: list[DocumentTypeCount]


class DependencyContributor(BaseModel):
    user_id: int
    name: str
    share: float


class DependencyTopicOut(BaseModel):
    topic_id: int
    topic_name: str
    contributors: list[DependencyContributor]
    concentration: str


class ContributionActivityOut(BaseModel):
    user_id: int
    name: str
    document_count: int
    topic_count: int
    last_activity: str | None = None
