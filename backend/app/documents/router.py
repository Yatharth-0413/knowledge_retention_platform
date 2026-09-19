import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import get_current_user
from app.config import settings
from app.database import get_db
from app.documents.chunking import chunk_text
from app.documents.extraction import ExtractionError, extract_text
from app.documents.models import Document, DocumentChunk, DocumentStatus, DocumentType
from app.documents.schemas import DocumentDetailOut, DocumentOut
from app.knowledge.service import embed_document_chunks, process_document_topics
from app.teams.access import require_team_access
from app.users.models import User

router = APIRouter(tags=["documents"])

_EXTENSION_TO_TYPE = {
    "pdf": DocumentType.PDF,
    "docx": DocumentType.DOCX,
    "xlsx": DocumentType.XLSX,
    "csv": DocumentType.CSV,
}


@router.post("/teams/{team_id}/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    team_id: int,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    require_team_access(team_id, current_user, db)

    extension = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    file_type = _EXTENSION_TO_TYPE.get(extension)
    if file_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Allowed: pdf, docx, xlsx, csv",
        )

    file_bytes = await file.read()

    team_dir = Path(settings.upload_dir) / str(team_id)
    team_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}.{extension}"
    stored_path = team_dir / stored_name
    stored_path.write_bytes(file_bytes)

    document = Document(
        team_id=team_id,
        uploaded_by_id=current_user.id,
        filename=file.filename or stored_name,
        file_type=file_type,
        file_path=str(stored_path),
        status=DocumentStatus.PROCESSING,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        # File parsing, topic extraction (Ollama) and embedding (sentence-transformers)
        # are all synchronous, potentially slow calls. Run them in FastAPI's threadpool
        # so a slow upload doesn't block the single event loop for every other request.
        text = await run_in_threadpool(extract_text, file_bytes, file_type)
        chunks = [
            DocumentChunk(document_id=document.id, chunk_index=index, content=content)
            for index, content in enumerate(chunk_text(text))
        ]
        db.add_all(chunks)
        document.status = DocumentStatus.READY
        db.flush()
        await run_in_threadpool(process_document_topics, db, document, text)
        await run_in_threadpool(embed_document_chunks, chunks)
    except ExtractionError as exc:
        document.status = DocumentStatus.FAILED
        document.error_message = str(exc)

    db.commit()
    db.refresh(document)
    return document


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
