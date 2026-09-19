"""RAG chat (README sections 13-14): embed the question, retrieve the closest
documented chunks for this team, ground an Ollama answer in them, and cite
sources + relevant contributors. Falls back to a plain "show the evidence"
response if Ollama isn't reachable, since it's a hackathon demo."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.chat.schemas import ChatContributorOut, ChatResponseOut, ChatSourceOut
from app.documents.models import Document, DocumentChunk, DocumentStatus
from app.knowledge.embeddings import embed_query
from app.knowledge.ollama_client import ollama_generate
from app.users.models import User

TOP_K = 5
MIN_SIMILARITY = 0.2  # cosine similarity below this is treated as "no real match"
EXCERPT_LENGTH = 280

_PROMPT = """You are the knowledge assistant for a team's internal documentation.
Answer the question using ONLY the context below. If the context does not contain
the answer, say you couldn't find enough documented information. Keep the answer
to 2-4 sentences and do not invent facts that aren't in the context.

Context:
{context}

Question: {question}

Answer:"""


@dataclass
class _RetrievedChunk:
    chunk: DocumentChunk
    document: Document
    similarity: float


def _retrieve(db: Session, team_id: int, question: str) -> list[_RetrievedChunk]:
    query_vector = embed_query(question)
    distance = DocumentChunk.embedding.cosine_distance(query_vector)

    rows = (
        db.query(DocumentChunk, Document, distance.label("distance"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .filter(
            Document.team_id == team_id,
            Document.status == DocumentStatus.READY,
            DocumentChunk.embedding.isnot(None),
        )
        .order_by(distance)
        .limit(TOP_K)
        .all()
    )
    return [
        _RetrievedChunk(chunk=chunk, document=document, similarity=1 - distance) for chunk, document, distance in rows
    ]


def answer_question(db: Session, team_id: int, question: str) -> ChatResponseOut:
    retrieved = [r for r in _retrieve(db, team_id, question) if r.similarity >= MIN_SIMILARITY]

    if not retrieved:
        return ChatResponseOut(
            answer="I couldn't find enough documented information to answer this confidently.",
            grounded=False,
            sources=[],
            contributors=[],
        )

    context = "\n\n".join(
        f"[{r.document.filename}]\n{r.chunk.content}" for r in retrieved
    )
    generated = ollama_generate(_PROMPT.format(context=context, question=question))
    if generated:
        answer = generated
        grounded = True
    else:
        answer = "AI generation isn't available right now, but here's the most relevant documented evidence:\n\n" + "\n\n".join(
            f"From {r.document.filename}: {r.chunk.content[:EXCERPT_LENGTH]}" for r in retrieved[:3]
        )
        grounded = False

    seen_documents: dict[int, Document] = {}
    for r in retrieved:
        seen_documents.setdefault(r.document.id, r.document)

    sources = [
        ChatSourceOut(document_id=r.document.id, filename=r.document.filename, excerpt=r.chunk.content[:EXCERPT_LENGTH])
        for r in retrieved
    ]

    contributor_ids = {doc.uploaded_by_id for doc in seen_documents.values()}
    contributors = [
        ChatContributorOut(user_id=user.id, name=user.name, designation=user.designation)
        for user in db.query(User).filter(User.id.in_(contributor_ids)).all()
    ]

    return ChatResponseOut(answer=answer, grounded=grounded, sources=sources, contributors=contributors)
