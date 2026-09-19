"""Local embeddings via sentence-transformers (README section 20 — no paid APIs).

The model is loaded lazily and cached at module scope so it's only downloaded/
loaded once per process, not once per request.
"""

from functools import lru_cache

from app.config import settings


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _get_model()
    return model.encode(texts, normalize_embeddings=True).tolist()


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
