"""LLM call tracing (Section 6: "self-hosted Langfuse or equivalent").

No-ops entirely unless `langfuse_enabled` is set and keys are present,
so local dev and CI never require a Langfuse account (per "do this for
no money" — nothing here costs anything until you opt in).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.core.config import get_settings


class NoopSpan:
    def update(self, **kwargs: Any) -> None:
        pass

    def end(self, **kwargs: Any) -> None:
        pass


_client: Any = None


def _get_client() -> Any:
    global _client
    settings = get_settings()
    if not settings.langfuse_enabled or not settings.langfuse_public_key:
        return None
    if _client is None:
        from langfuse import Langfuse  # imported lazily so it's an optional dep at runtime

        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    return _client


@contextmanager
def trace_llm_call(
    *, name: str, model: str, workspace_id: str, metadata: dict[str, Any] | None = None
) -> Iterator[NoopSpan]:
    """Wrap an LLM call. Logs prompt/output/tokens/cost/latency when a
    Langfuse client is configured; otherwise a silent no-op so the code
    path is identical in every environment."""
    client = _get_client()
    if client is None:
        yield NoopSpan()
        return

    generation = client.generation(
        name=name, model=model, metadata={"workspace_id": workspace_id, **(metadata or {})}
    )
    try:
        yield generation
    finally:
        generation.end()
