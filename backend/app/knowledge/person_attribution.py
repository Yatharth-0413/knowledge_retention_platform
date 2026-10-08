"""Row-level person attribution for structured documents (XLSX/CSV).

A roster-style spreadsheet (one row per team member) documents *other people's*
knowledge, not the uploader's. This matches each row's cells against the
uploading team's actual member list (generic - no hardcoded names, works for any
team) and, when a row names a known team member, treats the rest of that row's
text as evidence about *them* specifically, via DocumentTopic.subject_user_id.

Ordinary spreadsheets with no person-shaped rows fall through untouched - callers
treat an empty match list as "process this document the normal way."
"""

from sqlalchemy.orm import Session

from app.teams.access import team_user_ids
from app.users.models import User


def team_roster(db: Session, team) -> list[User]:
    """All people whose work counts for this team (members + the owning manager) -
    the same set `teams/access.py::team_user_ids` already treats as canonical."""
    return db.query(User).filter(User.id.in_(team_user_ids(team))).all()


def _match_cell_to_user(cell: str, roster: list[User]) -> User | None:
    cell_norm = cell.strip().lower()
    if not cell_norm:
        return None
    # Exact full name or email match first, so "Sriram Kumar" / his email never
    # gets shadowed by a different teammate's first name matching below.
    for user in roster:
        if cell_norm == user.email.lower() or cell_norm == user.name.strip().lower():
            return user
    # Fall back to a first-name-only match (the common case for a short roster
    # sheet, e.g. a cell that just says "sriram").
    for user in roster:
        tokens = user.name.strip().lower().split()
        if tokens and cell_norm == tokens[0]:
            return user
    return None


def match_rows_to_members(rows: list[list[str]], roster: list[User]) -> list[tuple[User, str]]:
    """For each row, check whether any cell identifies a team member. Returns
    (user, remaining_row_text) for each matched row - the matched name/email cell
    itself is excluded from remaining_row_text so topic extraction sees only the
    actual content ("working on agile low"), not the person's own name.

    Rows that don't match anyone (headers, unrelated sheets, etc.) are silently
    skipped - this is a best-effort signal, not a requirement that every row
    match.
    """
    matches: list[tuple[User, str]] = []
    for row in rows:
        matched_user: User | None = None
        remaining_cells: list[str] = []
        for cell in row:
            if matched_user is None:
                candidate = _match_cell_to_user(cell, roster)
                if candidate is not None:
                    matched_user = candidate
                    continue
            remaining_cells.append(cell)

        if matched_user is not None and remaining_cells:
            matches.append((matched_user, " ".join(remaining_cells)))
    return matches
