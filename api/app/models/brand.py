"""Brand Brain (Section 4.1, 7) — Phase 0 skeleton.

Full voice-model retrieval, offerings catalog, and rate cards land in
Phase 1-2. This captures the structural fields so the editor and
ingestion pipeline have a stable shape to build against.
"""

from pydantic import BaseModel, Field

from app.models.base import WorkspaceScopedDocument


class Bios(BaseModel):
    short_25_words: str = ""
    medium_75_words: str = ""
    long_250_words: str = ""


class AvailabilityRules(BaseModel):
    home_base: str = ""
    blackout_dates: list[str] = Field(default_factory=list)
    max_travel_days_per_month: int | None = None
    minimum_notice_days: int | None = None


class BusinessTerms(BaseModel):
    deposit_percent: int | None = None
    max_payment_terms_days: int | None = None
    cancellation_policy: str = ""
    travel_policy: str = ""


class Brand(WorkspaceScopedDocument):
    persona_name: str
    assistant_name: str = "Assistant"
    signature: str = ""  # e.g. "— Nova, AI booking assistant for Jane Doe"
    bios: Bios = Field(default_factory=Bios)
    media_kit_url: str = ""
    values: list[str] = Field(default_factory=list)
    no_go_categories: list[str] = Field(default_factory=list)
    availability: AvailabilityRules = Field(default_factory=AvailabilityRules)
    business_terms: BusinessTerms = Field(default_factory=BusinessTerms)
    is_active: bool = True

    class Settings:
        name = "brands"
        indexes = ["workspace_id"]
