from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str


class ChatSourceOut(BaseModel):
    document_id: int
    filename: str
    excerpt: str


class ChatContributorOut(BaseModel):
    user_id: int
    name: str
    designation: str | None = None


class ChatResponseOut(BaseModel):
    answer: str
    grounded: bool
    sources: list[ChatSourceOut]
    contributors: list[ChatContributorOut]
