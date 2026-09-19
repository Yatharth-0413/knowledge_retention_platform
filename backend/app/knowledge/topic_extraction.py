"""Topic extraction for uploaded documents (README section 5).

Primary path: ask the local Ollama LLM for a short list of topics. If Ollama
is unreachable or returns something unusable (common in a hackathon demo
where the local model isn't always running), fall back to a lightweight
frequency heuristic so the pipeline still produces topics.
"""

import json
import re
from collections import Counter

from app.knowledge.ollama_client import ollama_generate

MAX_TOPICS = 8

_PROMPT = """You extract technical and domain topics from internal team documents.
Read the document excerpt below and list the {max_topics} most important topics
(technologies, systems, processes, or subject areas) it documents.

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


def normalize_topic_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def extract_topics(text: str) -> list[str]:
    topics = _extract_via_ollama(text)
    if topics:
        return topics
    return _extract_via_heuristic(text)


def _extract_via_ollama(text: str) -> list[str]:
    excerpt = text[:4000]
    if not excerpt.strip():
        return []

    prompt = _PROMPT.format(max_topics=MAX_TOPICS, excerpt=excerpt)
    raw = ollama_generate(prompt, json_mode=True)
    if raw is None:
        return []
    try:
        parsed = json.loads(raw)
    except ValueError:
        return []
    if isinstance(parsed, dict):
        parsed = next((v for v in parsed.values() if isinstance(v, list)), [])
    if not isinstance(parsed, list):
        return []
    cleaned = [str(item).strip() for item in parsed if str(item).strip()]
    return cleaned[:MAX_TOPICS]


def _extract_via_heuristic(text: str) -> list[str]:
    """Frequency-based fallback: capitalized words/phrases that aren't stopwords."""
    candidates = re.findall(r"\b(?:[A-Z][a-zA-Z0-9+.#/-]*(?:\s+[A-Z][a-zA-Z0-9+.#/-]*){0,2})\b", text)
    counts: Counter[str] = Counter()
    for candidate in candidates:
        normalized = candidate.strip()
        if len(normalized) < 3:
            continue
        if normalized.lower() in _STOPWORDS:
            continue
        counts[normalized] += 1

    ranked = [name for name, count in counts.most_common(MAX_TOPICS * 2) if count > 1]
    if not ranked:
        ranked = [name for name, _ in counts.most_common(MAX_TOPICS)]
    return ranked[:MAX_TOPICS]
