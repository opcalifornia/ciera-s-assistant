"""EmbeddingProvider interface (Section 6).

`StubEmbeddingProvider` is free and deterministic: a feature-hashing
bag-of-words vector (SHA-256-hashed terms into a fixed-width vector).
It's not a real embedding model — it can't capture semantics — but it's
enough to make lexical similarity retrieval over Brand Brain documents
(voice samples, bios, past emails) actually work end-to-end with zero
API cost. `VoyageEmbeddingProvider` swaps in real embeddings once
`VOYAGE_API_KEY` is set (Section 6 decision: Voyage AI).
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from app.core.config import get_settings

VECTOR_DIM = 256
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _hash_index(token: str) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % VECTOR_DIM


class StubEmbeddingProvider:
    async def embed(self, text: str) -> list[float]:
        vector = [0.0] * VECTOR_DIM
        for token in _tokenize(text):
            vector[_hash_index(token)] += 1.0
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector


class VoyageEmbeddingProvider:
    """Real Voyage AI adapter, used once VOYAGE_API_KEY is configured."""

    def __init__(self, api_key: str) -> None:
        import voyageai

        self._client = voyageai.AsyncClient(api_key=api_key)

    async def embed(self, text: str) -> list[float]:
        result = await self._client.embed([text], model="voyage-3-lite")
        return list(result.embeddings[0])


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    global _provider
    if _provider is not None:
        return _provider
    settings = get_settings()
    if settings.voyage_api_key:
        _provider = VoyageEmbeddingProvider(settings.voyage_api_key)
    else:
        _provider = StubEmbeddingProvider()
    return _provider
