"""Eval fixture schema (Section 13).

Phase 0 ships the harness and fixture set with schema + coverage
validation only (no agents exist yet to grade). Phase 1 extends
`runner.py` to actually run the Triage/Brand Voice/Deal Desk agents
against these fixtures and score classification accuracy, field
extraction F1, and guardrail violations, per the metrics table in
Section 13.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class MessageClass(StrEnum):
    BRAND_DEAL = "brand_deal"
    SPEAKING = "speaking"
    SCHOOL_VISIT = "school_visit"
    SHOW_APPEARANCE = "show_appearance"
    MEDIA = "media"
    PRODUCTION_GIG = "production_gig"
    BOOK_ORDER = "book_order"
    COLLABORATION = "collaboration"
    OTHER = "other"
    FAN_MAIL = "fan_mail"
    PRESS_INQUIRY = "press_inquiry"
    VENDOR_PITCH = "vendor_pitch"
    SPAM = "spam"
    SCAM_SUSPECTED = "scam_suspected"
    PERSONAL = "personal"
    ADMIN_BILLING = "admin_billing"
    LEGAL = "legal"
    SUSPICIOUS_INJECTION = "suspicious_injection"


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
