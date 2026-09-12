"""Offerings catalog with rate cards (Section 4.1, 9.1, 9.2).

Modifiers and the concession ladder live directly on `Offering` rather
than a separate `rate_cards` collection — one offering has exactly one
rate card in practice, so splitting them would just be an extra join for
no real flexibility gained (graduating Phase 1's bare anchor/target/floor
into this richer shape without changing the collection, as planned).
"""

from enum import StrEnum

from pydantic import BaseModel, Field
from pymongo import IndexModel

from app.models.base import WorkspaceScopedDocument


class ModifierKind(StrEnum):
    ADDITIVE = "additive"  # `amount` is a flat currency delta
    MULTIPLICATIVE = "multiplicative"  # `amount` is a fraction, e.g. -0.15 = 15% off


class RateModifier(BaseModel):
    """One line of Section 9.1's modifier list — usage rights, exclusivity,
    rush delivery, travel days, virtual/nonprofit/Title I discounts,
    routing/bundle discounts, recording rights, etc. Generic on purpose:
    the talent configures which modifiers exist and their amounts rather
    than the code hardcoding each named modifier from the spec."""

    key: str  # stable id referenced by name when applying, e.g. "exclusivity_per_month"
    label: str
    kind: ModifierKind
    amount: float


class ConcessionRule(BaseModel):
    """One rung of Section 9.2's concession ladder: every price reduction
    is paired with a get. `fee_adjustment_pct` is negative (a discount),
    `requires` is the human-readable trade the other side must accept."""

    label: str
    fee_adjustment_pct: float
    requires: str


class BulkTier(BaseModel):
    """One rung of Section 9.1's bulk pricing model (`book_order`):
    quantity-based, not negotiation-based — there's no floor/target/
    anchor haggling, just 'buy more, pay less per unit'. `min_qty` is
    the smallest quantity this tier's `unit_price` applies to; tiers are
    matched by the highest `min_qty` at or below the requested quantity."""

    min_qty: int
    unit_price: float
    label: str = ""


class Offering(WorkspaceScopedDocument):
    brand_id: str
    opportunity_type: str  # Section 3 opportunity type id, e.g. "school_visit"
    name: str
    description: str = ""
    inclusions: list[str] = Field(default_factory=list)
    anchor: float | None = None
    target: float | None = None
    floor: float | None = None
    currency: str = "USD"
    modifiers: list[RateModifier] = Field(default_factory=list)
    concession_ladder: list[ConcessionRule] = Field(default_factory=list)
    bulk_tiers: list[BulkTier] = Field(default_factory=list)
    is_active: bool = True

    class Settings:
        name = "offerings"
        indexes = ["workspace_id", IndexModel([("brand_id", 1)])]
