"""Persisted option sets (Section 4.3.1, 7) and the choice log that
powers Section 4.3.4's future learning loop.

An `Option`/`QuickReply` embedded here mirrors `app.agents.schemas`
exactly — the agent schema is what the LLM/deterministic code produces;
this is what gets persisted and served to the approvals UI. Kept as two
separate types on purpose: the persisted shape gains fields (id, status)
the agent's output schema has no business knowing about.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field
from pymongo import IndexModel

from app.models.base import WorkspaceScopedDocument, utcnow


class OptionSetStatus(StrEnum):
    PENDING = "pending"
    CHOSEN = "chosen"
    SNOOZED = "snoozed"
    DISMISSED = "dismissed"


class PersistedOption(BaseModel):
    label: str
    strategy: str
    tradeoff: str
    likely_outcome: str
    draft: str
    numbers: dict[str, str] = Field(default_factory=dict)
    is_recommended: bool = False
    recommendation_reason: str = ""
    action: str
    policy_status: str
    policy_reason: str = ""


class PersistedQuickReply(BaseModel):
    label: str
    draft: str
    action: str
    policy_status: str
    policy_reason: str = ""


class OptionSet(WorkspaceScopedDocument):
    thread_id: str
    message_id: str = ""  # the inbound Message this option set responds to
    playbook_id: str | None = None
    options: list[PersistedOption] = Field(default_factory=list)
    quick_replies: list[PersistedQuickReply] = Field(default_factory=list)
    status: OptionSetStatus = OptionSetStatus.PENDING
    chosen_option_index: int | None = None  # index into `options`, or -1 for a quick reply
    snoozed_until: datetime | None = None

    class Settings:
        name = "option_sets"
        indexes = [
            "workspace_id",
            IndexModel([("thread_id", 1), ("created_at", -1)]),
        ]


class OptionChoiceOutcome(StrEnum):
    PENDING = "pending"  # not yet known
    REPLY_RECEIVED = "reply_received"
    NO_REPLY = "no_reply"
    WON = "won"
    LOST = "lost"


class OptionChoice(WorkspaceScopedDocument):
    """Section 4.3.4: log every option set, which option was chosen, edits,
    and the eventual outcome — this is the raw material for the future
    "make this the default?" learning loop (Phase 5)."""

    option_set_id: str
    playbook_id: str | None = None
    chosen_label: str
    was_edited: bool = False
    was_custom: bool = False  # "Write my own" rather than picking an option
    edit_distance: int = 0
    outcome: OptionChoiceOutcome = OptionChoiceOutcome.PENDING
    final_value: float | None = None
    chosen_by: str = ""  # user id
    chosen_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "option_choices"
        indexes = ["workspace_id", IndexModel([("option_set_id", 1)])]
