from pydantic import BaseModel


class TopicSummaryOut(BaseModel):
    id: int
    name: str
    contributor_count: int
    document_count: int


class TopicPersonEvidenceOut(BaseModel):
    user_id: int
    name: str
    designation: str | None = None
    score: float
    document_count: int


class TopicDocumentOut(BaseModel):
    id: int
    filename: str
    uploaded_by_id: int
    relevance: float


class TopicDetailOut(BaseModel):
    id: int
    name: str
    people: list[TopicPersonEvidenceOut]
    documents: list[TopicDocumentOut]


class UserTopicEvidenceOut(BaseModel):
    topic_id: int
    topic_name: str
    score: float
    document_count: int
