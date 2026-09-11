import json

import pytest

from app.agents.brand_voice import BrandVoiceAgent
from app.agents.schemas import MessageClass, TriageResult
from app.models.brand import Brand
from app.models.playbook import CompiledCriteria, FixedOption, ScenarioPlaybook
from tests.fakes import FakeLLMProvider

pytestmark = pytest.mark.asyncio


def make_brand() -> Brand:
    return Brand(workspace_id="ws1", persona_name="Jordan Rivers", assistant_name="Nova")


def make_triage(classification: MessageClass, **kwargs) -> TriageResult:
    return TriageResult(classification=classification, summary="s", **kwargs)


async def test_fan_mail_gets_quick_reply_not_option_set():
    llm = FakeLLMProvider(response_text="should never be called")
    agent = BrandVoiceAgent(llm)

    result = await agent.run(
        brand=make_brand(),
        triage=make_triage(MessageClass.FAN_MAIL),
        sender="fan@example.com",
        subject="You're amazing",
        body="Just wanted to say thanks!",
        workspace_id="ws1",
    )

    assert result.options == []
    assert len(result.quick_replies) == 1
    assert len(llm.calls) == 0  # never calls the LLM for simple messages


async def test_scam_suspected_always_needs_your_call():
    llm = FakeLLMProvider(response_text=json.dumps({"options": [{"label": "x"}]}))
    agent = BrandVoiceAgent(llm)

    result = await agent.run(
        brand=make_brand(),
        triage=make_triage(MessageClass.SCAM_SUSPECTED),
        sender="scam@example.com",
        subject="Check enclosed",
        body="...",
        workspace_id="ws1",
    )

    assert result.quick_replies[0].label == "Needs your call"
    assert len(llm.calls) == 0


async def test_valid_option_set_parses_and_marks_one_recommended():
    payload = {
        "options": [
            {
                "label": "Counter high",
                "strategy": "Anchor above target.",
                "tradeoff": "Risks losing the deal.",
                "likely_outcome": "They come back with a number.",
                "draft": "Thanks for reaching out...",
                "is_recommended": True,
                "recommendation_reason": "Best expected value.",
            },
            {
                "label": "Ask qualifying questions",
                "strategy": "Get more info before quoting.",
                "tradeoff": "Slower.",
                "likely_outcome": "They share more detail.",
                "draft": "A few quick questions first...",
            },
        ]
    }
    llm = FakeLLMProvider(response_text=json.dumps(payload))
    agent = BrandVoiceAgent(llm)

    result = await agent.run(
        brand=make_brand(),
        triage=make_triage(MessageClass.BRAND_DEAL, extracted_fields={"budget": "$500"}),
        sender="brand@example.com",
        subject="Partnership",
        body="We'd like to book something.",
        workspace_id="ws1",
    )

    assert len(result.options) == 2
    recommended = [o for o in result.options if o.is_recommended]
    assert len(recommended) == 1
    # policy_status must NOT be set by the agent (Section 4.3.1).
    assert all(o.policy_status is None for o in result.options)


async def test_unparseable_llm_output_falls_back_to_review_manually():
    llm = FakeLLMProvider(response_text="[stub:balanced] no LLM configured")
    agent = BrandVoiceAgent(llm)

    result = await agent.run(
        brand=make_brand(),
        triage=make_triage(MessageClass.BRAND_DEAL),
        sender="brand@example.com",
        subject="Partnership",
        body="...",
        workspace_id="ws1",
    )

    assert result.options == []
    assert result.quick_replies[0].label == "Review manually"


async def test_playbook_fixed_options_forced_into_system_prompt():
    playbook = ScenarioPlaybook(
        workspace_id="ws1",
        brand_id="b1",
        name="Rate ask",
        natural_language_trigger="when someone asks for my rate",
        compiled_criteria=CompiledCriteria(keywords=["rate"]),
        fixed_options=[
            FixedOption(label="Send rate card", strategy="Share pricing directly."),
            FixedOption(label="Ask budget first", strategy="Find their budget first."),
        ],
        allow_ai_extra_options=False,
    )
    payload = {
        "options": [
            {
                "label": "Send rate card",
                "strategy": "Share pricing directly.",
                "tradeoff": "-",
                "likely_outcome": "-",
                "draft": "Here's our rate card...",
                "is_recommended": True,
            },
            {
                "label": "Ask budget first",
                "strategy": "Find their budget first.",
                "tradeoff": "-",
                "likely_outcome": "-",
                "draft": "What's your budget?",
            },
        ]
    }
    llm = FakeLLMProvider(response_text=json.dumps(payload))
    agent = BrandVoiceAgent(llm)

    result = await agent.run(
        brand=make_brand(),
        triage=make_triage(MessageClass.BRAND_DEAL),
        sender="brand@example.com",
        subject="What's your rate?",
        body="What's your rate for a Reel?",
        workspace_id="ws1",
        playbook=playbook,
    )

    assert "Send rate card" in llm.calls[0]["system"]
    assert result.playbook_id == str(playbook.id)
    assert {o.label for o in result.options} == {"Send rate card", "Ask budget first"}
