"""Unit tests for app/documents/extraction.py's row-level helpers
(_csv_rows/_xlsx_rows/extract_rows) - the structured-row access that
person_attribution.py matches against the team roster, and the synthetic
'# Sheet:' marker-row filtering that was this session's Phase 1 header-leak fix."""

import io

import openpyxl
import pytest

from app.documents.extraction import ExtractionError, _csv_rows, _xlsx_rows, extract_rows, extract_text
from app.documents.models import DocumentType


def _make_xlsx_bytes(rows: list[list[str]], *, sheet_title: str = "Sheet1") -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = sheet_title
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_csv_rows_parses_simple_rows():
    csv_bytes = b"Name,Notes\nAlice,Working on Agile\nBob,Leading DevOps\n"
    rows = _csv_rows(csv_bytes)
    assert rows == [["Name", "Notes"], ["Alice", "Working on Agile"], ["Bob", "Leading DevOps"]]


def test_csv_rows_skips_fully_blank_rows():
    csv_bytes = b"Name,Notes\nAlice,Working on Agile\n\n,\nBob,Leading DevOps\n"
    rows = _csv_rows(csv_bytes)
    assert [r for r in rows if r == ["Alice", "Working on Agile"]]
    assert all(any(cell.strip() for cell in row) for row in rows)


def test_extract_rows_for_csv_matches_csv_rows():
    csv_bytes = b"Name,Notes\nAlice,Working on Agile\n"
    assert extract_rows(csv_bytes, DocumentType.CSV) == _csv_rows(csv_bytes)


def test_xlsx_rows_prefixes_each_sheet_with_a_marker_row():
    xlsx_bytes = _make_xlsx_bytes([["Alice", "Working on Agile"]], sheet_title="Team Info")
    rows = _xlsx_rows(xlsx_bytes)
    assert rows[0] == ["# Sheet: Team Info"]
    assert ["Alice", "Working on Agile"] in rows


def test_extract_rows_for_xlsx_filters_out_the_sheet_marker_row():
    # This is the Phase 1 header-leak regression guard: extract_rows must never
    # hand person_attribution.py a synthetic "# Sheet: ..." row to match against.
    xlsx_bytes = _make_xlsx_bytes([["Alice", "Working on Agile"]], sheet_title="Team Info")
    rows = extract_rows(xlsx_bytes, DocumentType.XLSX)
    assert all(not (len(row) == 1 and row[0].startswith("# Sheet:")) for row in rows)
    assert ["Alice", "Working on Agile"] in rows


def test_extract_rows_for_xlsx_skips_fully_blank_data_rows():
    xlsx_bytes = _make_xlsx_bytes([["Alice", "Working on Agile"], [None, None], ["Bob", "Leading DevOps"]])
    rows = extract_rows(xlsx_bytes, DocumentType.XLSX)
    assert ["Alice", "Working on Agile"] in rows
    assert ["Bob", "Leading DevOps"] in rows
    assert [] not in rows


def test_extract_text_raises_extraction_error_for_unsupported_type():
    # extract_text only handles PDF/DOCX/XLSX/CSV - EMAIL bodies are parsed via a
    # separate path (email_parser.py), so this must fail loudly, not silently.
    with pytest.raises(ExtractionError):
        extract_text(b"irrelevant", DocumentType.EMAIL)
