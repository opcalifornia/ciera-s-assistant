"""Unified inbox: Thread + Message (Section 4.2, 7).

A Thread is channel-agnostic — email, sms, dm, or intake — so triage,
option sets, and approvals work identically regardless of where a
message came from (PLAN.md Section 7 addendum: "know what's an email vs
a text, respond either way, in the same app").
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from pymongo import IndexModel

from app.models.base import WorkspaceScopedDocument, utcnow


class Channel(StrEnum):
    EMAIL = "email"
    SMS = "sms"
    DM = "dm"
    INTAKE = "intake"


class MessageDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class TriageSnapshot(BaseModel):
    """Cached copy of the latest Triage agent result, denormalized onto
    the thread so inbox list views don't need a second query per row."""

    classification: str = ""
    opportunity_type: str | None = None
    summary: str = ""
    urgency: str = "normal"  # low | normal | high
    estimated_deal_value: float | None = None
    flags: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    recommended_next_action: str = ""
    confidence: float = 0.0


class Thread(WorkspaceScopedDocument):
    brand_id: str
    channel: Channel
    provider_thread_id: str = ""  # e.g. Gmail thread id, Twilio conversation sid
    participants: list[str] = Field(default_factory=list)  # emails or phone numbers
    subject: str = ""
    last_message_at: datetime = Field(default_factory=utcnow)
    triage: TriageSnapshot | None = None
    needs_a_look: bool = False  # low-confidence classification lane (Section 4.2)
    archived: bool = False

    class Settings:
        name = "threads"
        indexes = [
            "workspace_id",
            IndexModel([("workspace_id", 1), ("last_message_at", -1)]),
        ]


class Message(WorkspaceScopedDocument):
    thread_id: str
    direction: MessageDirection
    channel: Channel
    sender: str
    recipients: list[str] = Field(default_factory=list)
    subject: str = ""
    body_text: str
    sent_or_received_at: datetime = Field(default_factory=utcnow)
    injection_flag: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)  # provider message id, etc.

    class Settings:
        name = "messages"
        indexes = [
            "workspace_id",
            IndexModel([("thread_id", 1), ("sent_or_received_at", 1)]),
        ]
