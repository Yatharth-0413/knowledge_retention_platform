"""Thin client for the local Ollama LLM (README section 20 — no paid APIs).

Every caller must treat a None return as "Ollama isn't available right now"
and fall back to something reasonable — this is a hackathon demo and the
local model won't always be running.
"""

import httpx

from app.config import settings

_TIMEOUT = httpx.Timeout(90.0, connect=3.0)


def ollama_generate(prompt: str, *, json_mode: bool = False, num_predict: int = 256) -> str | None:
    """num_predict caps the response length. Without it, `format: json` only constrains the
    output to be *valid* JSON, not short — a small model can ramble for hundreds of tokens
    answering an 8-item topic list, which on CPU-only inference risks blowing the client
    timeout below and silently degrading to the non-AI fallback. Callers should pass a cap
    sized to what they actually expect back (a short topic array vs a 2-4 sentence answer).
    """
    try:
        response = httpx.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": num_predict},
                **({"format": "json"} if json_mode else {}),
            },
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip() or None
    except httpx.HTTPError:
        return None
