"""Opportunity pipeline (Section 7, 9.3).

One `Opportunity` per deal-shaped thread — created the moment Triage
classifies a message as one of the opportunity types (Section 3), and
carried forward by the Deal Desk agent as the thread progresses.

Stage transitions to `VERBAL_YES` and beyond always require talent
approval (Section 9.3) — enforced by the Policy Engine, not here; this
module only defines the legal transitions so nothing can skip stages.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import Field
from pymongo import IndexModel

from app.models.base import WorkspaceScopedDocument


class OpportunityStage(StrEnum):
    NEW = "new"
    QUALIFYING = "qualifying"
    QUOTED = "quoted"
    COUNTERING = "countering"
    VERBAL_YES = "verbal_yes"
    CONTRACTING = "contracting"
    DEPOSIT_PENDING = "deposit_pending"
    CONFIRMED = "confirmed"
    DELIVERED = "delivered"
    INVOICED = "invoiced"
    PAID = "paid"
    FEEDBACK_COLLECTED = "feedback_collected"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"
    DECLINED_BY_TALENT = "declined_by_talent"
    GHOSTED = "ghosted"
    ON_HOLD = "on_hold"

    @property
    def is_terminal(self) -> bool:
        return self in (
            OpportunityStage.CLOSED_WON,
            OpportunityStage.CLOSED_LOST,
            OpportunityStage.DECLINED_BY_TALENT,
            OpportunityStage.GHOSTED,
        )


# Section 9.3's linear happy path. Any stage can also move directly to
# CLOSED_LOST / DECLINED_BY_TALENT / GHOSTED / ON_HOLD (handled as a
# special case in `can_transition`, not enumerated here to avoid an
# explosion of redundant edges).
_HAPPY_PATH: list[OpportunityStage] = [
    OpportunityStage.NEW,
    OpportunityStage.QUALIFYING,
    OpportunityStage.QUOTED,
    OpportunityStage.COUNTERING,
    OpportunityStage.VERBAL_YES,
    OpportunityStage.CONTRACTING,
    OpportunityStage.DEPOSIT_PENDING,
    OpportunityStage.CONFIRMED,
    OpportunityStage.DELIVERED,
    OpportunityStage.INVOICED,
    OpportunityStage.PAID,
    OpportunityStage.FEEDBACK_COLLECTED,
    OpportunityStage.CLOSED_WON,
]

# Stages where re-quoting/countering can loop back to QUOTED/COUNTERING
# rather than strictly advancing (a negotiation goes back and forth).
_NEGOTIATION_STAGES = {OpportunityStage.QUOTED, OpportunityStage.COUNTERING}

_ALWAYS_REACHABLE = {
    OpportunityStage.CLOSED_LOST,
    OpportunityStage.DECLINED_BY_TALENT,
    OpportunityStage.GHOSTED,
    OpportunityStage.ON_HOLD,
}

# Approval-gated stages (Section 9.3: "Stage transitions to verbal_yes
# and beyond always require talent approval").
APPROVAL_GATED_STAGES = frozenset(
    {
        OpportunityStage.VERBAL_YES,
        OpportunityStage.CONTRACTING,
        OpportunityStage.DEPOSIT_PENDING,
        OpportunityStage.CONFIRMED,
    }
)


def can_transition(current: OpportunityStage, target: OpportunityStage) -> bool:
    if current.is_terminal:
        return False
    if target in _ALWAYS_REACHABLE:
        return True
    if current in _NEGOTIATION_STAGES and target in _NEGOTIATION_STAGES:
        return True
    if current not in _HAPPY_PATH or target not in _HAPPY_PATH:
        return False
    return _HAPPY_PATH.index(target) == _HAPPY_PATH.index(current) + 1


class Opportunity(WorkspaceScopedDocument):
    brand_id: str
    thread_id: str
    opportunity_type: str  # Section 3 type id, e.g. "brand_deal"
    stage: OpportunityStage = OpportunityStage.NEW
    extracted_fields: dict[str, str] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    est_value: float | None = None
    quoted_value: float | None = None
    final_value: float | None = None
    fit_score: float | None = None
    risk_flags: list[str] = Field(default_factory=list)
    next_action: str = ""
    due_at: datetime | None = None
    owner_user_id: str | None = None

    class Settings:
        name = "opportunities"
        indexes = [
            "workspace_id",
            IndexModel([("thread_id", 1)]),
            IndexModel([("brand_id", 1), ("stage", 1)]),
        ]
