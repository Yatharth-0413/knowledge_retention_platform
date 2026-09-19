"""Thin client for the local Ollama LLM (README section 20 — no paid APIs).

Every caller must treat a None return as "Ollama isn't available right now"
and fall back to something reasonable — this is a hackathon demo and the
local model won't always be running.
"""

import httpx

from app.config import settings

_TIMEOUT = httpx.Timeout(30.0, connect=3.0)


def ollama_generate(prompt: str, *, json_mode: bool = False) -> str | None:
    try:
        response = httpx.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                **({"format": "json"} if json_mode else {}),
            },
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip() or None
    except httpx.HTTPError:
        return None
