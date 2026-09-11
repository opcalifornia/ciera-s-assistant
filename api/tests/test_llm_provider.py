from app.core.config import get_settings
from app.core.models_config import ModelTier
from app.providers.llm import StubLLMProvider, get_llm_provider


async def test_stub_provider_is_default_without_api_key():
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.anthropic_api_key == ""
    provider = get_llm_provider()
    assert isinstance(provider, StubLLMProvider)


async def test_stub_provider_never_calls_network():
    provider = StubLLMProvider()
    response = await provider.complete(
        system="You are Nova.",
        messages=[{"role": "user", "content": "What's your rate for a keynote?"}],
        tier=ModelTier.BALANCED,
        workspace_id="ws_1",
    )
    assert "stub" in response.text
    assert response.model  # tier mapping resolved even without a live call
