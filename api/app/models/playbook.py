"""Scenario Playbooks (Section 4.3.2).

`compiled_criteria` is Phase 1's deterministic, free match target:
keywords, sender domains, and opportunity types. The full spec also
imagines an LLM-compiled `classifier_description` for fuzzier natural-
language triggers — that's a real upgrade path (swap in an LLM call to
widen matching) but isn't required for the keyword/domain matching this
ships with, so it's stored but unused until a later phase wires it up.
"""

from pydantic import BaseModel, Field
from pymongo import IndexModel

from app.models.base import WorkspaceScopedDocument


class CompiledCriteria(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    sender_domains: list[str] = Field(default_factory=list)
    opportunity_types: list[str] = Field(default_factory=list)
    min_value: float | None = None
    max_value: float | None = None
    classifier_description: str = ""  # reserved for future LLM-based matching


class FixedOption(BaseModel):
    label: str
    strategy: str
    template: str = ""  # optional draft template; blank = agent fills it in


class ScenarioPlaybook(WorkspaceScopedDocument):
    brand_id: str
    name: str
    natural_language_trigger: str
    compiled_criteria: CompiledCriteria = Field(default_factory=CompiledCriteria)
    fixed_options: list[FixedOption] = Field(default_factory=list)
    allow_ai_extra_options: bool = True
    notification_priority: str = "normal"  # low | normal | high
    enabled: bool = True
    is_default: bool = False

    class Settings:
        name = "scenario_playbooks"
        indexes = ["workspace_id", IndexModel([("brand_id", 1), ("enabled", 1)])]
