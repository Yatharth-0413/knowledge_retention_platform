"""Topic extraction for uploaded documents (README section 5).

Primary path: ask the local Ollama LLM for a short list of topics. If Ollama
is unreachable or returns something unusable (common in a hackathon demo
where the local model isn't always running), fall back to a lightweight
frequency heuristic so the pipeline still produces topics.
"""

import json
import logging
import re
from collections import Counter

from app.knowledge.ollama_client import ollama_generate

logger = logging.getLogger(__name__)

MAX_TOPICS = 8

_PROMPT = """You extract technical and domain topics from internal team documents.
A topic is a domain concept the document provides evidence someone knows: a
technology, system, process, skill, or subject area (e.g. "Kubernetes", "Java
Threads", "Agile", "Database Optimization"). A topic is NEVER a verb, a filler
word, a generic noun, or a structural label from the document's own formatting
(e.g. "occurs", "working", "every", "information", "this", "process", "sheet",
"document", "subject").

Bad extraction (do not do this):
  Text: "Deployment occurs every Friday. Working on java threads."
  Bad:  ["occurs", "Deployment occurs", "Working", "every"]
  Good: ["Deployment", "Java Threads"]

Read the document excerpt below and list up to {max_topics} topics it documents,
most important first.

Respond with ONLY a JSON array of short topic strings, e.g. ["Kubernetes", "CI/CD", "Risk Engine"].
No explanation, no markdown, just the JSON array.

Document excerpt:
\"\"\"
{excerpt}
\"\"\"
"""

_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "into", "your", "their",
    "will", "have", "has", "are", "was", "were", "been", "being", "not", "but",
    "you", "our", "its", "they", "them", "all", "any", "can", "should", "must",
    "when", "then", "than", "also", "each", "more", "such", "use", "used", "using",
}

# The heuristic fallback (no semantic understanding at all) is especially prone to
# picking up a capitalized verb/filler as if it were a topic - e.g. "Deployment
# Occurs" from "Deployment occurs every Friday". Drop any candidate whose first
# word is one of these, since a real topic is never introduced with a bare verb or
# filler word. Not exhaustive by design (this is a last-resort fallback, not the
# primary extraction path) - just removes the most common junk.
_LEADING_WORD_BLOCKLIST = {
    "occurs", "occurring", "working", "worked", "works", "using", "used", "uses",
    "every", "this", "that", "these", "those", "information", "process",
    "processing", "document", "documents", "sheet", "subject", "from", "date",
    "being", "doing", "done", "making", "made", "running", "runs",
}


def normalize_topic_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def extract_topics(text: str) -> list[str]:
    topics = _extract_via_ollama(text)
    if topics:
        return topics
    # Quality silently degrades here - no few-shot/semantic guidance at all - so
    # this is worth a log line (not a user-facing warning, out of scope here) for
    # anyone debugging why a document's topics look off.
    logger.warning("Ollama topic extraction unavailable/empty; falling back to heuristic extraction")
    return _extract_via_heuristic(text)


_OLLAMA_ATTEMPTS = 2  # one retry: llama3.2 is sampled (temperature 0.8), so a single
# malformed/looping response on short, sparse input (observed in testing - e.g. a
# repeated-key JSON blob that gets cut off mid-token by num_predict) is often just
# bad luck, not a systematic failure. A second attempt costs one more ~20s call but
# avoids falling all the way back to the heuristic (which has zero semantic
# understanding) for what the model would have answered correctly on a retry.


def _extract_via_ollama(text: str) -> list[str]:
    excerpt = text[:4000]
    if not excerpt.strip():
        return []

    prompt = _PROMPT.format(max_topics=MAX_TOPICS, excerpt=excerpt)
    for attempt in range(_OLLAMA_ATTEMPTS):
        topics = _one_ollama_attempt(prompt)
        if topics:
            return topics
    return []


_DICT_KEY_PATTERN = re.compile(r'"((?:[^"\\]|\\.)+)"\s*:')


def _salvage_keys(raw: str) -> list[str]:
    """Observed in testing: on short/sparse input, llama3.2 sometimes lists far
    more than 8 candidate topics as JSON object keys (e.g.
    `{"DevOps":"", "High":"", "Java Threads":"", ...`) and gets cut off by
    num_predict before closing the object - a real topic list, just truncated
    into invalid JSON. Rather than discard it, pull out whatever quoted keys are
    present; this is only ever reached after json.loads has already failed.
    """
    return [m.group(1) for m in _DICT_KEY_PATTERN.finditer(raw)]


def _one_ollama_attempt(prompt: str) -> list[str]:
    # 220 tokens: generous enough for the model to finish closing a verbose
    # object response (see _salvage_keys) without reopening the risk the num_predict
    # cap exists to prevent - unbounded generation blowing the client timeout.
    raw = ollama_generate(prompt, json_mode=True, num_predict=220)
    if raw is None:
        return []
    try:
        parsed = json.loads(raw)
    except ValueError:
        salvaged = _salvage_keys(raw)
        return salvaged[:MAX_TOPICS] if salvaged else []
    if isinstance(parsed, dict):
        # json_mode constrains the model to *valid JSON*, not necessarily the
        # requested array shape - on short/ambiguous input it sometimes returns
        # e.g. {"Agile": null} instead of ["Agile"] despite correctly identifying
        # the topic. Prefer a nested list value if there is one; otherwise the
        # dict's own keys are the topic names.
        list_value = next((v for v in parsed.values() if isinstance(v, list)), None)
        parsed = list_value if list_value is not None else list(parsed.keys())
    if not isinstance(parsed, list):
        return []
    cleaned = [str(item).strip() for item in parsed if str(item).strip()]
    return cleaned[:MAX_TOPICS]


def _extract_via_heuristic(text: str) -> list[str]:
    """Frequency-based fallback: capitalized words/phrases that aren't stopwords
    or obvious verbs/filler (see _LEADING_WORD_BLOCKLIST). No semantic
    understanding - this only runs when Ollama is unreachable."""
    candidates = re.findall(r"\b(?:[A-Z][a-zA-Z0-9+.#/-]*(?:\s+[A-Z][a-zA-Z0-9+.#/-]*){0,2})\b", text)
    counts: Counter[str] = Counter()
    for candidate in candidates:
        normalized = candidate.strip()
        if len(normalized) < 3:
            continue
        if normalized.lower() in _STOPWORDS:
            continue
        first_word = normalized.split()[0].lower()
        if first_word in _LEADING_WORD_BLOCKLIST:
            continue
        counts[normalized] += 1

    ranked = [name for name, count in counts.most_common(MAX_TOPICS * 2) if count > 1]
    if not ranked:
        ranked = [name for name, _ in counts.most_common(MAX_TOPICS)]
    return ranked[:MAX_TOPICS]
