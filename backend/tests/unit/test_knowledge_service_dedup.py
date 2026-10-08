"""Unit tests for app/knowledge/service.py's topic dedup logic
(_get_or_create_topic / _find_similar_topic) - the embedding-similarity merge
added this session so "Deployment" / "Deployment Approval" / "DevOps Deployment"
collapse into one topic instead of tripling. embed_query/embed_texts are
monkeypatched out so these tests never load the real sentence-transformers model.
"""

from unittest.mock import MagicMock

from app.knowledge.service import _TOPIC_SIMILARITY_THRESHOLD, _find_similar_topic, _get_or_create_topic
from app.knowledge.models import Topic


def _chainable(**terminal):
    mock = MagicMock()
    mock.join.return_value = mock
    mock.filter.return_value = mock
    mock.order_by.return_value = mock
    for name, value in terminal.items():
        setattr(mock, name, MagicMock(return_value=value))
    return mock


def test_find_similar_topic_reuses_topic_above_threshold():
    existing = Topic(id=1, name="Deployment", normalized_name="deployment")
    # distance just small enough that (1 - distance) clears the threshold.
    distance = 1 - (_TOPIC_SIMILARITY_THRESHOLD + 0.01)
    db = MagicMock()
    db.query.return_value = _chainable(first=(existing, distance))

    result = _find_similar_topic(db, [0.1] * 384)

    assert result is existing


def test_find_similar_topic_rejects_below_threshold():
    existing = Topic(id=1, name="JavaScript", normalized_name="javascript")
    # distance just large enough that (1 - distance) misses the threshold -
    # e.g. "Java" must not silently merge into "JavaScript".
    distance = 1 - (_TOPIC_SIMILARITY_THRESHOLD - 0.01)
    db = MagicMock()
    db.query.return_value = _chainable(first=(existing, distance))

    assert _find_similar_topic(db, [0.1] * 384) is None


def test_find_similar_topic_returns_none_when_no_topics_exist_yet():
    db = MagicMock()
    db.query.return_value = _chainable(first=None)

    assert _find_similar_topic(db, [0.1] * 384) is None


def test_get_or_create_topic_reuses_exact_normalized_match(monkeypatch):
    existing = Topic(id=1, name="Kubernetes", normalized_name="kubernetes")
    db = MagicMock()
    db.query.return_value = _chainable(first=existing)
    embed_mock = MagicMock()
    monkeypatch.setattr("app.knowledge.service.embed_query", embed_mock)

    result = _get_or_create_topic(db, "Kubernetes")

    assert result is existing
    db.add.assert_not_called()
    embed_mock.assert_not_called()  # exact match short-circuits before any embedding call


def test_get_or_create_topic_reuses_embedding_similar_topic(monkeypatch):
    existing = Topic(id=2, name="Deployment", normalized_name="deployment")
    db = MagicMock()
    db.query.return_value = _chainable(first=None)  # no exact normalized-name match
    monkeypatch.setattr("app.knowledge.service.embed_query", lambda name: [0.1] * 384)
    monkeypatch.setattr("app.knowledge.service._find_similar_topic", lambda db, embedding: existing)

    result = _get_or_create_topic(db, "Deployment Approval")

    assert result is existing
    db.add.assert_not_called()


def test_get_or_create_topic_creates_new_topic_when_nothing_matches(monkeypatch):
    db = MagicMock()
    db.query.return_value = _chainable(first=None)
    monkeypatch.setattr("app.knowledge.service.embed_query", lambda name: [0.1] * 384)
    monkeypatch.setattr("app.knowledge.service._find_similar_topic", lambda db, embedding: None)

    result = _get_or_create_topic(db, "  Risk Engine  ")

    assert result.name == "Risk Engine"
    assert result.normalized_name == "risk engine"
    db.add.assert_called_once_with(result)
    db.flush.assert_called_once()
