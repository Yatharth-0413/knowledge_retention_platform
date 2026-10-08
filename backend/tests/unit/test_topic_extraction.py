"""Unit tests for app/knowledge/topic_extraction.py: the normalization used for
topic dedup, the heuristic fallback's verb/filler filtering (the "(sheet)" /
"occurs" bug class fixed this session), the truncated-JSON salvage regex, and
the Ollama response parser's handling of the dict-shaped/truncated responses
found during this session's testing.
"""

from app.knowledge.topic_extraction import (
    MAX_TOPICS,
    _extract_via_heuristic,
    _one_ollama_attempt,
    _salvage_keys,
    normalize_topic_name,
)


def test_normalize_topic_name_lowercases_and_trims():
    assert normalize_topic_name("  Kubernetes  ") == "kubernetes"


def test_normalize_topic_name_collapses_internal_whitespace():
    assert normalize_topic_name("Java   Threads\n\tDeep Dive") == "java threads deep dive"


def test_extract_via_heuristic_excludes_leading_verbs_and_fillers():
    # The exact repro from this session's bug report: "Deployment occurs every
    # Friday. Working on Java Threads." must not extract "occurs"/"Working" as
    # if they were topics.
    text = "Deployment occurs every Friday. Working on Java Threads."
    topics = _extract_via_heuristic(text)
    assert not any(t.lower().startswith("occurs") for t in topics)
    assert not any(t.lower().startswith("working") for t in topics)


def test_extract_via_heuristic_keeps_real_multi_word_topics():
    text = "Deployment occurs every Friday. Working on Java Threads."
    topics = _extract_via_heuristic(text)
    assert "Deployment" in topics
    assert "Java Threads" in topics


def test_extract_via_heuristic_ranks_repeated_phrases_first():
    text = (
        "Kubernetes is used for orchestration. The Kubernetes cluster runs CI/CD jobs. "
        "Kubernetes upgrades happen quarterly. A one-off mention of Grafana."
    )
    topics = _extract_via_heuristic(text)
    assert topics[0] == "Kubernetes"


def test_extract_via_heuristic_drops_short_candidates():
    # A 2-character candidate ("CI" on its own, not merged into a longer phrase)
    # is below the length-3 floor and must be dropped even if it repeats.
    text = "We use CI daily. CI runs reliably, CI is stable."
    topics = _extract_via_heuristic(text)
    assert "CI" not in topics


def test_extract_via_heuristic_caps_at_max_topics():
    text = " ".join(f"Topic{n} SubPart" for n in range(MAX_TOPICS + 10))
    topics = _extract_via_heuristic(text)
    assert len(topics) <= MAX_TOPICS


def test_salvage_keys_extracts_quoted_keys_from_truncated_json():
    # Observed in testing: llama3.2 sometimes lists many candidate topics as dict
    # keys and gets cut off by num_predict before closing the object.
    raw = '{"DevOps": "", "High": "", "Java Threads": "", "Risk Eng'
    assert _salvage_keys(raw) == ["DevOps", "High", "Java Threads"]


def test_salvage_keys_returns_empty_for_no_keys():
    assert _salvage_keys("not json at all") == []


def test_one_ollama_attempt_parses_plain_json_array(monkeypatch):
    monkeypatch.setattr(
        "app.knowledge.topic_extraction.ollama_generate", lambda *a, **k: '["Kubernetes", "CI/CD"]'
    )
    assert _one_ollama_attempt("prompt") == ["Kubernetes", "CI/CD"]


def test_one_ollama_attempt_prefers_nested_list_in_dict_response(monkeypatch):
    monkeypatch.setattr(
        "app.knowledge.topic_extraction.ollama_generate", lambda *a, **k: '{"topics": ["Agile"]}'
    )
    assert _one_ollama_attempt("prompt") == ["Agile"]


def test_one_ollama_attempt_falls_back_to_dict_keys_when_no_list_value(monkeypatch):
    # Observed bug: json_mode guarantees valid JSON, not the requested shape -
    # on sparse input the model sometimes returns {"Agile": null} instead of
    # ["Agile"].
    monkeypatch.setattr(
        "app.knowledge.topic_extraction.ollama_generate", lambda *a, **k: '{"Agile": null, "DevOps": null}'
    )
    assert _one_ollama_attempt("prompt") == ["Agile", "DevOps"]


def test_one_ollama_attempt_salvages_truncated_json(monkeypatch):
    monkeypatch.setattr(
        "app.knowledge.topic_extraction.ollama_generate",
        lambda *a, **k: '{"DevOps": "", "Java Threads": "", "Risk Eng',
    )
    assert _one_ollama_attempt("prompt") == ["DevOps", "Java Threads"]


def test_one_ollama_attempt_returns_empty_when_ollama_unavailable(monkeypatch):
    monkeypatch.setattr("app.knowledge.topic_extraction.ollama_generate", lambda *a, **k: None)
    assert _one_ollama_attempt("prompt") == []


def test_one_ollama_attempt_returns_empty_for_non_list_non_dict_json(monkeypatch):
    monkeypatch.setattr("app.knowledge.topic_extraction.ollama_generate", lambda *a, **k: "42")
    assert _one_ollama_attempt("prompt") == []
