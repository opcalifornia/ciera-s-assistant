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
