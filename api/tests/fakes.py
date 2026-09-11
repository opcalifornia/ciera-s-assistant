"""Deterministic, network-free test doubles."""

from app.core.models_config import ModelTier
from app.providers.llm import LLMResponse


class FakeLLMProvider:
    """Returns a preset response regardless of input — lets tests exercise
    an agent's parsing/fallback logic without any real LLM call."""

    def __init__(self, response_text: str = "") -> None:
        self.response_text = response_text
        self.calls: list[dict] = []

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        tier: ModelTier,
        workspace_id: str,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        self.calls.append(
            {"system": system, "messages": messages, "tier": tier, "workspace_id": workspace_id}
        )
        return LLMResponse(text=self.response_text, model=f"fake-{tier.value}")


class ScriptedLLMProvider:
    """Returns different canned responses depending on which agent is
    calling (matched by a substring unique to that agent's system
    prompt) — needed because a single pipeline run calls the LLM once
    for Triage and once for Brand Voice, and each expects a differently
    shaped JSON response. `routes` is checked in order; the first
    substring match wins."""

    def __init__(self, routes: list[tuple[str, str]]) -> None:
        self.routes = routes
        self.calls: list[dict] = []

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        tier: ModelTier,
        workspace_id: str,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        self.calls.append({"system": system, "messages": messages, "tier": tier})
        for needle, response_text in self.routes:
            if needle in system:
                return LLMResponse(text=response_text, model=f"fake-{tier.value}")
        return LLMResponse(text="", model=f"fake-{tier.value}")
