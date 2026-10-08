"""Unit tests for app/knowledge/scoring.py.

_freshness_score/_freshness_label are pure and tested directly. recompute_evidence
talks to the DB, so it's tested with a mocked Session whose query chain is stubbed
to return canned rows in the exact call order the function makes them in - brittle
to implementation reordering, but it lets this core scoring algorithm (including
the new freshness_label, added this session and deliberately kept distinct from
the 0-100 score) be verified without a live database.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.knowledge.scoring import _freshness_label, _freshness_score, recompute_evidence


def _chainable(**terminal):
    """A MagicMock whose join()/filter()/order_by() all return itself, so any
    chain length collapses to just configuring the final call's return value."""
    mock = MagicMock()
    mock.join.return_value = mock
    mock.filter.return_value = mock
    mock.order_by.return_value = mock
    for name, value in terminal.items():
        setattr(mock, name, MagicMock(return_value=value))
    return mock


def _utc(days_ago: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


def test_freshness_score_within_30_days_is_full():
    assert _freshness_score(_utc(0)) == 100.0
    assert _freshness_score(_utc(30)) == 100.0


def test_freshness_score_31_to_90_days_is_medium():
    assert _freshness_score(_utc(31)) == 60.0
    assert _freshness_score(_utc(90)) == 60.0


def test_freshness_score_over_90_days_is_low():
    assert _freshness_score(_utc(91)) == 30.0


def test_freshness_label_boundaries_match_freshness_score_boundaries():
    assert _freshness_label(_utc(30)) == "New"
    assert _freshness_label(_utc(31)) == "Medium"
    assert _freshness_label(_utc(90)) == "Medium"
    assert _freshness_label(_utc(91)) == "Old"


def test_freshness_score_handles_naive_datetime():
    # most_recent can come from a column without tzinfo in some code paths -
    # must not raise TypeError when subtracting an aware "now" from a naive value.
    naive_recent = datetime.now() - timedelta(days=5)
    assert _freshness_score(naive_recent) == 100.0


def test_recompute_evidence_deletes_and_returns_none_when_no_contributing_documents():
    db = MagicMock()
    empty_rows_query = _chainable(all=[])
    delete_query = _chainable()
    db.query.side_effect = [empty_rows_query, delete_query]

    result = recompute_evidence(db, user_id=1, topic_id=1)

    assert result is None
    delete_query.delete.assert_called_once()


def test_recompute_evidence_creates_new_evidence_with_score_and_freshness():
    db = MagicMock()

    doc = MagicMock()
    doc.id = 1
    doc.created_at = _utc(0)  # fresh -> New

    rows_query = _chainable(all=[(doc, 1.0)])
    depth_query = _chainable(scalar=5)
    existing_evidence_query = _chainable(first=None)
    db.query.side_effect = [rows_query, depth_query, existing_evidence_query]

    evidence = recompute_evidence(db, user_id=1, topic_id=1)

    assert evidence is not None
    assert evidence.freshness_label == "New"
    assert 0.0 <= evidence.score <= 100.0
    db.add.assert_called_once_with(evidence)


def test_recompute_evidence_updates_existing_evidence_in_place():
    db = MagicMock()

    doc = MagicMock()
    doc.id = 1
    doc.created_at = _utc(120)  # stale -> Old

    rows_query = _chainable(all=[(doc, 0.5)])
    depth_query = _chainable(scalar=0)
    existing = MagicMock(score=99.0, document_count=99, freshness_label="New")
    existing_evidence_query = _chainable(first=existing)
    db.query.side_effect = [rows_query, depth_query, existing_evidence_query]

    evidence = recompute_evidence(db, user_id=1, topic_id=1)

    assert evidence is existing
    assert evidence.freshness_label == "Old"
    assert evidence.score < 99.0  # recomputed down from the stale canned value
    db.add.assert_not_called()  # updated in place, not re-added
