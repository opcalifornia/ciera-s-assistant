"""Eval fixture schema (Section 13).

Phase 0 shipped the harness and fixture set with schema + coverage
validation only. Phase 1 wires `runner.py` to actually run the Triage
agent against these fixtures and score classification accuracy — see
`evals/scoring.py`. `MessageClass` is imported from `app.agents.schemas`
so the fixtures and the real agent are validated against the exact same
classification set.
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from app.agents.schemas import MessageClass

__all__ = ["MessageClass", "EvalCategory", "ThreadFixture", "ExpectedOutcome", "EvalFixture"]


class EvalCategory(StrEnum):
    BRAND_DEAL = "brand_deal"
    SPEAKING = "speaking"
    SCHOOL = "school"
    SHOW_MEDIA = "show_media"
    PRODUCTION = "production"
    SAFETY = "safety"


class ThreadFixture(BaseModel):
    subject: str
    body: str
    sender: str = "unknown@example.com"


class ExpectedOutcome(BaseModel):
    classification: MessageClass
    # Section 2 hard rails a correct response must never violate for this fixture.
    must_never: list[str] = Field(default_factory=list)
    notes: str = ""


class EvalFixture(BaseModel):
    id: str
    category: EvalCategory
    opportunity_type: str | None = None
    thread: ThreadFixture
    expected: ExpectedOutcome
