"""RAG chat (README sections 13-14): embed the question, retrieve the closest
documented chunks for this team, ground an Ollama answer in them, and cite
sources + relevant contributors. Falls back to a plain "show the evidence"
response if Ollama isn't reachable, since it's a hackathon demo.

Also does entity-aware retrieval (see _match_question_to_people /
_evidence_context): embedding similarity alone is unreliable for "What does
<name> know?" questions - a short proper-noun query can score just above or
below MIN_SIMILARITY against the same shared chunk almost arbitrarily (a
general-purpose sentence embedding model weakly discriminates between proper
nouns). When the question names a known team member (or refers to the asker via
"I"/"my"), their documented KnowledgeEvidence is pulled directly from the
database - ground truth, not a retrieval guess - and blended into the same
retrieval/context/sources pipeline used for everything else.
"""

import re
from dataclasses import dataclass

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.chat.schemas import ChatContributorOut, ChatResponseOut, ChatSourceOut
from app.documents.models import Document, DocumentChunk, DocumentStatus
from app.knowledge.embeddings import embed_query
from app.knowledge.models import DocumentTopic, KnowledgeEvidence, Topic
from app.knowledge.ollama_client import ollama_generate
from app.knowledge.person_attribution import team_roster
from app.teams.models import Team
from app.users.models import User

TOP_K = 5
MAX_EVIDENCE_DOCS = 5
MIN_SIMILARITY = 0.2  # cosine similarity below this is treated as "no real match"
EXCERPT_LENGTH = 280

_SELF_REFERENCE = re.compile(r"\b(i|my|me|myself)\b", re.I)

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


def _match_question_to_people(question: str, roster: list[User], current_user: User) -> list[User]:
    """Which team members (if any) this question is actually about - matched
    generically against the real roster, never a hardcoded name list. Checked as
    whole-word matches (full name, then first name) so "Sri" can't false-positive
    inside "Sriram". Falls back to the asker themselves on a first-person
    reference ("what do I know", "my knowledge") when no one is named.
    """
    q_lower = question.lower()
    matched: list[User] = []
    for user in roster:
        name = user.name.strip().lower()
        if not name:
            continue
        tokens = name.split()
        candidates = {name, tokens[0]}
        if any(re.search(rf"\b{re.escape(c)}\b", q_lower) for c in candidates):
            matched.append(user)
    if matched:
        return matched
    if _SELF_REFERENCE.search(q_lower):
        return [current_user]
    return []


def _evidence_context(
    db: Session, team: Team, question: str, current_user: User
) -> tuple[list[_RetrievedChunk], str, list[User]]:
    """Ground-truth retrieval for named-person questions: pull the matched
    person's KnowledgeEvidence directly (same query shape as
    knowledge/router.py::get_user_knowledge) instead of hoping embedding search
    happens to surface the right chunk. Returns extra chunk-like results (one per
    contributing document, so they flow through the normal sources/contributors
    pipeline unchanged) plus a structured summary to prepend to the LLM context.
    """
    roster = team_roster(db, team)
    matched_people = _match_question_to_people(question, roster, current_user)
    if not matched_people:
        return [], "", []

    extra_chunks: list[_RetrievedChunk] = []
    summary_lines: list[str] = []
    seen_chunk_ids: set[int] = set()

    for person in matched_people:
        evidence_rows = (
            db.query(KnowledgeEvidence, Topic)
            .join(Topic, Topic.id == KnowledgeEvidence.topic_id)
            .filter(KnowledgeEvidence.user_id == person.id)
            .order_by(KnowledgeEvidence.score.desc())
            .all()
        )
        if not evidence_rows:
            summary_lines.append(f"{person.name}: no documented knowledge evidence found.")
            continue

        topic_summaries = [f"{topic.name} ({evidence.score:.0f}% documented evidence)" for evidence, topic in evidence_rows]
        summary_lines.append(f"{person.name}: " + ", ".join(topic_summaries))

        topic_ids = [topic.id for _, topic in evidence_rows]
        doc_rows = (
            db.query(Document)
            .join(DocumentTopic, DocumentTopic.document_id == Document.id)
            .filter(
                Document.team_id == team.id,
                Document.status == DocumentStatus.READY,
                DocumentTopic.topic_id.in_(topic_ids),
                or_(
                    DocumentTopic.subject_user_id == person.id,
                    and_(DocumentTopic.subject_user_id.is_(None), Document.uploaded_by_id == person.id),
                ),
            )
            .distinct()
            .limit(MAX_EVIDENCE_DOCS)
            .all()
        )
        for document in doc_rows:
            chunk = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.document_id == document.id)
                .order_by(DocumentChunk.chunk_index)
                .first()
            )
            if chunk is not None and chunk.id not in seen_chunk_ids:
                seen_chunk_ids.add(chunk.id)
                extra_chunks.append(_RetrievedChunk(chunk=chunk, document=document, similarity=1.0))

    summary = "Documented knowledge evidence on file:\n" + "\n".join(summary_lines)
    return extra_chunks, summary, matched_people


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


def answer_question(db: Session, team_id: int, question: str, current_user: User) -> ChatResponseOut:
    team = db.get(Team, team_id)
    vector_retrieved = [r for r in _retrieve(db, team_id, question) if r.similarity >= MIN_SIMILARITY]
    evidence_chunks, evidence_summary, matched_people = _evidence_context(db, team, question, current_user)

    # Evidence-matched chunks first (they're ground truth for a named-person
    # question, not a similarity guess), then whatever vector search also found.
    seen_chunk_ids: set[int] = set()
    retrieved: list[_RetrievedChunk] = []
    for r in evidence_chunks + vector_retrieved:
        if r.chunk.id in seen_chunk_ids:
            continue
        seen_chunk_ids.add(r.chunk.id)
        retrieved.append(r)

    if not retrieved and not evidence_summary:
        return ChatResponseOut(
            answer="I couldn't find enough documented information to answer this confidently.",
            grounded=False,
            sources=[],
            contributors=[],
        )

    context_blocks = ([evidence_summary] if evidence_summary else []) + [
        f"[{r.document.filename}]\n{r.chunk.content}" for r in retrieved
    ]
    context = "\n\n".join(context_blocks)
    # The prompt asks for 2-4 sentences; 300 tokens is generous headroom without letting a
    # rambling response risk the client timeout on slow CPU-only inference.
    generated = ollama_generate(_PROMPT.format(context=context, question=question), num_predict=300)
    if generated:
        answer = generated
        grounded = True
    elif retrieved:
        answer = "AI generation isn't available right now, but here's the most relevant documented evidence:\n\n" + "\n\n".join(
            f"From {r.document.filename}: {r.chunk.content[:EXCERPT_LENGTH]}" for r in retrieved[:3]
        )
        grounded = False
    else:
        answer = "AI generation isn't available right now, but here's the most relevant documented evidence:\n\n" + evidence_summary
        grounded = False

    seen_documents: dict[int, Document] = {}
    for r in retrieved:
        seen_documents.setdefault(r.document.id, r.document)

    sources = [
        ChatSourceOut(document_id=r.document.id, filename=r.document.filename, excerpt=r.chunk.content[:EXCERPT_LENGTH])
        for r in retrieved
    ]

    # The relevant contributor for "what does <name> know" is <name> themselves,
    # not necessarily whoever uploaded the file their evidence came from (e.g. a
    # manager uploading a team roster on someone else's behalf - see
    # knowledge/person_attribution.py).
    contributor_ids = {doc.uploaded_by_id for doc in seen_documents.values()} | {person.id for person in matched_people}
    contributors = [
        ChatContributorOut(user_id=user.id, name=user.name, designation=user.designation)
        for user in db.query(User).filter(User.id.in_(contributor_ids)).all()
    ]

    return ChatResponseOut(answer=answer, grounded=grounded, sources=sources, contributors=contributors)
