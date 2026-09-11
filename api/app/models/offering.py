"""Offerings catalog (Section 4.1).

Full rate cards with modifiers and a concession ladder are Section 9 /
Phase 2 (Deal Desk). Phase 1's `Offering` carries the anchor/target/floor
numbers directly so the Brand Brain editor and the seed data (PLAN.md
Section 16) have somewhere to live now — Phase 2 can graduate these into
a full `RateCard` with modifiers without changing this shape.
"""

from pydantic import Field
from pymongo import IndexModel

from app.models.base import WorkspaceScopedDocument


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
    is_active: bool = True

    class Settings:
        name = "offerings"
        indexes = ["workspace_id", IndexModel([("brand_id", 1)])]
