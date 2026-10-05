import uuid
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import get_current_user
from app.config import settings
from app.database import get_db
from app.documents.chunking import chunk_text
from app.documents.email_parser import EmailParseError, parse_outlook_file
from app.documents.extraction import extract_text
from app.documents.models import Document, DocumentChunk, DocumentStatus, DocumentType
from app.documents.schemas import DocumentDetailOut, DocumentOut, EmailAttachmentOut, EmailIngestOut
from app.knowledge.service import embed_document_chunks, process_document_topics
from app.teams.access import require_team_access, team_user_ids
from app.users.models import User

router = APIRouter(tags=["documents"])

_EXTENSION_TO_TYPE = {
    "pdf": DocumentType.PDF,
    "docx": DocumentType.DOCX,
    "xlsx": DocumentType.XLSX,
    "csv": DocumentType.CSV,
}
_EMAIL_EXTENSIONS = {"msg", "eml"}


def _save_file(team_id: int, file_bytes: bytes, extension: str) -> Path:
    team_dir = Path(settings.upload_dir) / str(team_id)
    team_dir.mkdir(parents=True, exist_ok=True)
    stored_path = team_dir / f"{uuid.uuid4().hex}.{extension}"
    stored_path.write_bytes(file_bytes)
    return stored_path


async def _run_pipeline(db: Session, document: Document, get_text: Callable[[], str]) -> int:
    """Extract -> chunk -> topics -> embeddings for one document; returns the chunk count.

    Runs inside a savepoint so any failure (not just ExtractionError) marks the
    document FAILED instead of leaving it stuck in PROCESSING with a half-written session.
    Parsing, topic extraction (Ollama) and embedding are slow synchronous calls, so they run
    in the threadpool to keep the event loop free for other requests.
    """
    try:
        with db.begin_nested():
            text = await run_in_threadpool(get_text)
            chunks = [
                DocumentChunk(document_id=document.id, chunk_index=index, content=content)
                for index, content in enumerate(chunk_text(text))
            ]
            db.add_all(chunks)
            document.status = DocumentStatus.READY
            db.flush()
            await run_in_threadpool(process_document_topics, db, document, text)
            await run_in_threadpool(embed_document_chunks, chunks)
        return len(chunks)
    except Exception as exc:  # noqa: BLE001 - any pipeline failure is recorded on the document
        document.status = DocumentStatus.FAILED
        document.error_message = str(exc)
        return 0


def _new_document(
    team_id: int,
    owner_id: int,
    filename: str,
    file_type: DocumentType,
    path: Path,
    parent_id: int | None = None,
) -> Document:
    return Document(
        team_id=team_id,
        uploaded_by_id=owner_id,
        filename=filename[:255],
        file_type=file_type,
        file_path=str(path),
        status=DocumentStatus.PROCESSING,
        parent_document_id=parent_id,
    )


@router.post(
    "/teams/{team_id}/documents",
    response_model=DocumentOut | EmailIngestOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    team_id: int,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document | EmailIngestOut:
    team = require_team_access(team_id, current_user, db)

    filename = file.filename or ""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    file_bytes = await file.read()

    if extension in _EMAIL_EXTENSIONS:
        return await _ingest_email(db, team, current_user, filename, extension, file_bytes)

    file_type = _EXTENSION_TO_TYPE.get(extension)
    if file_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Allowed: pdf, docx, xlsx, csv, msg, eml",
        )

    stored_path = _save_file(team_id, file_bytes, extension)
    document = _new_document(team_id, current_user.id, filename or stored_path.name, file_type, stored_path)
    db.add(document)
    db.commit()
    db.refresh(document)

    await _run_pipeline(db, document, lambda: extract_text(file_bytes, file_type))

    db.commit()
    db.refresh(document)
    return document


async def _ingest_email(
    db: Session, team, uploader: User, filename: str, extension: str, file_bytes: bytes
) -> EmailIngestOut:
    """Ingest a .msg/.eml: the cleaned body becomes an EMAIL document and each
    supported attachment becomes a child document run through the normal pipeline."""
    try:
        parsed = await run_in_threadpool(parse_outlook_file, file_bytes, filename)
    except EmailParseError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    # Credit the email to its sender when they belong to this team; otherwise to the uploader.
    owner_id = uploader.id
    if parsed["sender_email"]:
        sender = db.query(User).filter(User.email == parsed["sender_email"], User.id.in_(team_user_ids(team))).first()
        if sender is not None:
            owner_id = sender.id

    subject = parsed["subject"] or "(no subject)"
    sent_on = parsed["date"].isoformat() if parsed["date"] else "unknown"
    sender_label = f'{parsed["sender_name"]} <{parsed["sender_email"]}>'.strip()
    # Header lines go first: topic extraction only reads the head of the text.
    email_text = f"Subject: {subject}\nFrom: {sender_label}\nDate: {sent_on}\n\n{parsed['body']}".strip()

    email_document = _new_document(
        team.id, owner_id, f"Email: {subject}", DocumentType.EMAIL, _save_file(team.id, file_bytes, extension)
    )
    db.add(email_document)
    db.commit()
    db.refresh(email_document)
    body_chunk_count = await _run_pipeline(db, email_document, lambda: email_text)
    db.commit()

    processed: list[EmailAttachmentOut] = []
    skipped: list[EmailAttachmentOut] = []
    for att_name, att_bytes in parsed["attachments"]:
        att_ext = att_name.rsplit(".", 1)[-1].lower() if "." in att_name else ""
        att_type = _EXTENSION_TO_TYPE.get(att_ext)
        if att_type is None:
            skipped.append(EmailAttachmentOut(filename=att_name, status="skipped", detail="Unsupported attachment type"))
            continue

        child = _new_document(
            team.id, owner_id, att_name, att_type, _save_file(team.id, att_bytes, att_ext), email_document.id
        )
        db.add(child)
        db.commit()
        db.refresh(child)
        await _run_pipeline(db, child, lambda: extract_text(att_bytes, att_type))
        db.commit()

        if child.status == DocumentStatus.READY:
            processed.append(EmailAttachmentOut(filename=att_name, status="processed", document_id=child.id))
        else:
            skipped.append(
                EmailAttachmentOut(filename=att_name, status="failed", document_id=child.id, detail=child.error_message)
            )

    db.refresh(email_document)
    return EmailIngestOut(
        document=DocumentOut.model_validate(email_document),
        subject=subject,
        sender_email=parsed["sender_email"],
        sender_name=parsed["sender_name"],
        body_chunk_count=body_chunk_count,
        attachments_processed=processed,
        attachments_skipped=skipped,
    )


@router.get("/teams/{team_id}/documents", response_model=list[DocumentOut])
def list_team_documents(
    team_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Document]:
    require_team_access(team_id, current_user, db)
    return db.query(Document).filter(Document.team_id == team_id).order_by(Document.created_at.desc()).all()


@router.get("/documents/{document_id}", response_model=DocumentDetailOut)
def get_document(
    document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    require_team_access(document.team_id, current_user, db)
    return document
