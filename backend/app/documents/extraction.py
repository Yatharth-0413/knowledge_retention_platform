"""Text extraction for uploaded documents.

Perfect fidelity is not the goal here (see the project README, section 4) —
just enough structured text for chunking and downstream topic/embedding work.
"""

import csv
import io

import openpyxl
import pymupdf
from docx import Document as DocxDocument

from app.documents.models import DocumentType


class ExtractionError(Exception):
    pass


def extract_text(file_bytes: bytes, file_type: DocumentType) -> str:
    try:
        if file_type == DocumentType.PDF:
            return _extract_pdf(file_bytes)
        if file_type == DocumentType.DOCX:
            return _extract_docx(file_bytes)
        if file_type == DocumentType.XLSX:
            return _extract_xlsx(file_bytes)
        if file_type == DocumentType.CSV:
            return _extract_csv(file_bytes)
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller as a processing failure
        raise ExtractionError(str(exc)) from exc
    raise ExtractionError(f"Unsupported file type: {file_type}")


def _extract_pdf(file_bytes: bytes) -> str:
    with pymupdf.open(stream=file_bytes, filetype="pdf") as pdf:
        pages = [page.get_text() for page in pdf]
    return "\n\n".join(pages).strip()


def _extract_docx(file_bytes: bytes) -> str:
    doc = DocxDocument(io.BytesIO(file_bytes))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return "\n".join(parts).strip()


def _extract_xlsx(file_bytes: bytes) -> str:
    workbook = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
    parts = []
    for sheet in workbook.worksheets:
        parts.append(f"# Sheet: {sheet.title}")
        for row in sheet.iter_rows(values_only=True):
            cells = [str(v) for v in row if v is not None]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts).strip()


def _extract_csv(file_bytes: bytes) -> str:
    text = file_bytes.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    return "\n".join(" | ".join(row) for row in reader if any(cell.strip() for cell in row)).strip()
