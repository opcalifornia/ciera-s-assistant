"""Canonical structured-output schemas for agents (Section 3, 5, 13).

`evals/schema.py` imports `MessageClass` from here so the eval fixtures
and the real Triage agent are validated against the exact same
classification set — no drift between what we test and what we ship.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class MessageClass(StrEnum):
    """Every inbound message is one of these (Section 3)."""

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


OPPORTUNITY_CLASSES = frozenset(
    {
        MessageClass.BRAND_DEAL,
        MessageClass.SPEAKING,
        MessageClass.SCHOOL_VISIT,
        MessageClass.SHOW_APPEARANCE,
        MessageClass.MEDIA,
        MessageClass.PRODUCTION_GIG,
        MessageClass.BOOK_ORDER,
        MessageClass.COLLABORATION,
    }
)


class Urgency(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class TriageResult(BaseModel):
    classification: MessageClass
    summary: str = Field(max_length=400)  # "≤3 lines" per Section 4.2
    extracted_fields: dict[str, str] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    urgency: Urgency = Urgency.NORMAL
    estimated_deal_value: float | None = None
    fit_score: float | None = None  # 0-1, fit against Brand Brain values/no-gos
    flags: set[str] = Field(default_factory=set)
    recommended_next_action: str = ""
    confidence: float = 0.5  # 0-1

    @property
    def opportunity_type(self) -> str | None:
        return self.classification.value if self.classification in OPPORTUNITY_CLASSES else None

    @property
    def needs_a_look(self) -> bool:
        """Section 4.2: low-confidence classifications go to a 'Needs a
        look' lane rather than guessing."""
        return self.confidence < 0.55 or "low_confidence" in self.flags


class ReplyOption(BaseModel):
    label: str  # 2-4 word goal-oriented name
    strategy: str  # one sentence on what this move does
    tradeoff: str
    likely_outcome: str
    draft: str
    numbers: dict[str, str] = Field(default_factory=dict)
    is_recommended: bool = False
    recommendation_reason: str = ""
    action: str = "message.send_reply"  # Policy Engine action id
    # Populated by the router after calling the Policy Engine — never set
    # by the agent itself (Section 4.3.1: "computed by the Policy Engine,
    # never by the LLM").
    policy_status: str | None = None
    policy_reason: str = ""


class QuickReply(BaseModel):
    label: str
    draft: str
    action: str = "message.send_acknowledgment"
    policy_status: str | None = None
    policy_reason: str = ""


class OptionSetResult(BaseModel):
    options: list[ReplyOption] = Field(default_factory=list)
    quick_replies: list[QuickReply] = Field(default_factory=list)
    playbook_id: str | None = None
