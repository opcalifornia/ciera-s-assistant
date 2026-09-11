"""Workspace: the tenant boundary (Section 7)."""

from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.base import TimestampedDocument


class AutonomyLevel(StrEnum):
    """Section 11 — default is L0 for everything, everywhere."""

    L0_DRAFT_ONLY = "L0"
    L1_AUTO_SEND_LOW_STAKES = "L1"
    L2_AUTO_NEGOTIATE_WITHIN_RAILS = "L2"


class AutonomyConfig(BaseModel):
    """Per-opportunity-type autonomy override. Missing keys default to L0."""

    default: AutonomyLevel = AutonomyLevel.L0_DRAFT_ONLY
    by_opportunity_type: dict[str, AutonomyLevel] = Field(default_factory=dict)

    def level_for(self, opportunity_type: str | None) -> AutonomyLevel:
        if opportunity_type and opportunity_type in self.by_opportunity_type:
            return self.by_opportunity_type[opportunity_type]
        return self.default


class WorkspaceSettings(BaseModel):
    timezone: str = "America/Los_Angeles"
    quiet_hours_start: str = "21:00"
    quiet_hours_end: str = "08:00"


class Workspace(TimestampedDocument):
    name: str
    plan: str = "founder"
    settings: WorkspaceSettings = Field(default_factory=WorkspaceSettings)
    autonomy: AutonomyConfig = Field(default_factory=AutonomyConfig)
    kill_switch: bool = False

    class Settings:
        name = "workspaces"
