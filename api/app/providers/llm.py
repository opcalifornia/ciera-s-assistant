"""LLMProvider interface (Section 5, Section 6 principle: "every external
integration sits behind an interface so vendors can be swapped without
touching business logic").

`StubLLMProvider` is the default so agents can be built and tested with
zero API cost; `AnthropicLLMProvider` is a thin, swappable adapter over
the real API, used only when `ANTHROPIC_API_KEY` is configured.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.core.config import get_settings
from app.core.models_config import ModelTier, model_for_tier
from app.core.tracing import trace_llm_call


class LLMMessage(Protocol):
    role: str
    content: str


class LLMResponse:
    def __init__(
        self, text: str, *, model: str, input_tokens: int = 0, output_tokens: int = 0
    ) -> None:
        self.text = text
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class LLMProvider(Protocol):
    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        tier: ModelTier,
        workspace_id: str,
        max_tokens: int = 1024,
    ) -> LLMResponse: ...


class StubLLMProvider:
    """Deterministic, free, offline provider for dev/tests/CI.

    Never calls out to any network or paid API. Echoes a fixed shape so
    downstream code (schema validation, policy engine wiring) can be
    exercised without an API key.
    """

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        tier: ModelTier,
        workspace_id: str,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        model = model_for_tier(tier)
        with trace_llm_call(name="stub.complete", model=model, workspace_id=workspace_id):
            last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
            return LLMResponse(
                text=f"[stub:{tier.value}] no LLM configured — echoing input: {last_user[:200]}",
                model=model,
            )


class AnthropicLLMProvider:
    """Real Anthropic-backed provider. Only instantiate this once billing
    is set up — see `get_llm_provider()` below for the gate."""

    def __init__(self, api_key: str) -> None:
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        tier: ModelTier,
        workspace_id: str,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        model = model_for_tier(tier)
        with trace_llm_call(
            name="anthropic.complete", model=model, workspace_id=workspace_id
        ) as span:
            response = await self._client.messages.create(
                model=model,
                system=system,
                messages=messages,  # type: ignore[arg-type]
                max_tokens=max_tokens,
            )
            text = "".join(block.text for block in response.content if block.type == "text")
            span.update(
                usage={
                    "input": response.usage.input_tokens,
                    "output": response.usage.output_tokens,
                }
            )
            return LLMResponse(
                text=text,
                model=model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )


_provider: Any = None


def get_llm_provider() -> LLMProvider:
    """Factory: returns the free stub unless a real API key is configured.
    This is the single switch that turns on LLM spend for the whole app."""
    global _provider
    if _provider is not None:
        return _provider
    settings = get_settings()
    if settings.anthropic_api_key:
        _provider = AnthropicLLMProvider(settings.anthropic_api_key)
    else:
        _provider = StubLLMProvider()
    return _provider
