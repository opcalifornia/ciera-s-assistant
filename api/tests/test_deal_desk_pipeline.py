"""Proves Deal Desk grounds the Brand Voice agent's option set with real
numbers, end to end through `ingest_inbound_message` — not just the
isolated units tested elsewhere. Uses `ScriptedLLMProvider` so Triage
gets a valid `brand_deal` classification (the free `StubLLMProvider`
alone can't produce one, since its text doesn't parse as JSON) while
Brand Voice still exercises real JSON parsing + grounded-option merging.
"""

import json

import pytest

from app.models.brand import Brand
from app.models.offering import ConcessionRule, Offering
from app.models.thread import Channel
from app.models.workspace import Workspace
from app.services import pipeline_service
from tests.fakes import ScriptedLLMProvider

pytestmark = pytest.mark.asyncio

TRIAGE_JSON = json.dumps(
    {
        "classification": "brand_deal",
        "summary": "Brand wants a sponsored Reel.",
        "extracted_fields": {"budget": "$1850"},
        "missing_fields": [],
        "urgency": "normal",
        "confidence": 0.9,
    }
)

BRAND_VOICE_JSON = json.dumps(
    {
        "options": [
            {
                "label": "Ask qualifying questions",
                "strategy": "Get more detail before committing.",
                "tradeoff": "Slower.",
                "likely_outcome": "They share more detail.",
                "draft": "A few quick questions first...",
            }
        ]
    }
)


async def _setup() -> tuple[Workspace, Brand]:
    workspace = Workspace(name="Deal Desk Pipeline Test")
    await workspace.insert()
    brand = Brand(workspace_id=str(workspace.id), persona_name="Test Talent", signature="— Nova")
    await brand.insert()
    offering = Offering(
        workspace_id=str(workspace.id),
        brand_id=str(brand.id),
        opportunity_type="brand_deal",
        name="Sponsored Reel",
        anchor=3000,
        target=2000,
        floor=1200,
        concession_ladder=[
            ConcessionRule(
                label="Shorter usage window", fee_adjustment_pct=-0.1, requires="usage <= 90 days"
            )
        ],
    )
    await offering.insert()
    return workspace, brand


async def test_grounded_option_anchors_the_set_and_llm_adds_extra_options(monkeypatch):
    workspace, brand = await _setup()
    fake_llm = ScriptedLLMProvider(
        routes=[("Triage agent", TRIAGE_JSON), ("Brand Voice agent", BRAND_VOICE_JSON)]
    )
    monkeypatch.setattr(pipeline_service, "get_llm_provider", lambda: fake_llm)

    thread, message, option_set = await pipeline_service.ingest_inbound_message(
        workspace_id=str(workspace.id),
        brand=brand,
        channel=Channel.EMAIL,
        sender="brand@wellknownco.example.com",
        subject="Partnership",
        body="We'd like to book a Reel. Budget is $1850.",
    )

    assert thread.triage is not None
    assert thread.triage.classification == "brand_deal"

    labels = [o.label for o in option_set.options]
    assert labels[0] == "Counter with a trade"  # grounded option always first/recommended
    assert "Ask qualifying questions" in labels  # LLM's extra option preserved
    assert option_set.options[0].is_recommended is True
    assert option_set.options[1].is_recommended is False

    grounded = option_set.options[0]
    assert "1,800" in grounded.draft
    assert grounded.action == "message.send_counter_within_concession_ladder_above_target"


async def test_grounded_option_used_even_when_llm_output_unparseable(monkeypatch):
    workspace, brand = await _setup()
    fake_llm = ScriptedLLMProvider(
        routes=[("Triage agent", TRIAGE_JSON), ("Brand Voice agent", "not valid json")]
    )
    monkeypatch.setattr(pipeline_service, "get_llm_provider", lambda: fake_llm)

    _thread, _message, option_set = await pipeline_service.ingest_inbound_message(
        workspace_id=str(workspace.id),
        brand=brand,
        channel=Channel.EMAIL,
        sender="brand@example.com",
        subject="Partnership",
        body="Budget is $1850.",
    )

    assert len(option_set.options) == 1
    assert option_set.options[0].label == "Counter with a trade"
    assert option_set.options[0].policy_status == "require_approval"
