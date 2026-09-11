"""Model tier -> Anthropic model ID mapping (Section 5).

This is the ONLY place model IDs are hardcoded. Verify current IDs and
pricing at https://docs.claude.com before changing this mapping.
"""

from enum import StrEnum


class ModelTier(StrEnum):
    FAST = "fast"  # Triage, scam/injection screening, scheduler
    BALANCED = "balanced"  # Brand Voice, Prospector, Outreach Writer, Briefing
    CAPABLE = "capable"  # Deal Desk, Contracts


MODEL_MAP: dict[ModelTier, str] = {
    ModelTier.FAST: "claude-haiku-4-5-20251001",
    ModelTier.BALANCED: "claude-sonnet-5",
    ModelTier.CAPABLE: "claude-opus-5",
}


def model_for_tier(tier: ModelTier) -> str:
    return MODEL_MAP[tier]
