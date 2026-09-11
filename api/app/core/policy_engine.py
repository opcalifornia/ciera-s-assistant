"""The Policy Engine (Section 2 principle 2, Section 5, Section 11).

Plain, deterministic code. No agent or LLM output ever reaches a
SIDE_EFFECT tool without passing through `evaluate`. This module has
zero dependency on any LLM provider.

Phase 0 implements the gate itself plus the always-DENY hard rails and
the autonomy-level check. Rail checks that need rate-card/thread state
(floor violations, exclusivity detection, etc.) land in Phase 2 as the
Deal Desk agent's outputs start flowing through here — the shape of
`PolicyRequest.payload` already anticipates those fields.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.models.workspace import AutonomyLevel, Workspace


class ToolPermissionClass(StrEnum):
    READ = "read"
    DRAFT = "draft"
    SIDE_EFFECT = "side_effect"
    NEVER = "never"


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


# Actions no autonomy level ever auto-sends (Section 11 "Never automated").
HARD_DENY_ACTIONS: frozenset[str] = frozenset(
    {
        "contract.sign",
        "invoice.refund",
        "workspace.change_autonomy_settings",
        "rate_card.change_floor",
        "opportunity.accept_final_terms",
    }
)

# Side-effect actions L1 is allowed to auto-send (Section 11).
L1_ALLOWED_ACTIONS: frozenset[str] = frozenset(
    {
        "message.send_acknowledgment",
        "message.send_intake_redirect",
        "message.send_faq_answer",
        "message.send_decline_no_go",
        "message.send_decline_spam",
        "calendar.schedule_within_availability",
    }
)

# Additional side-effect actions L2 unlocks, ON TOP of everything L1 allows
# (Section 11: negotiate within rails, at or above target only).
L2_ADDITIONAL_ACTIONS: frozenset[str] = frozenset(
    {
        "message.request_missing_info",
        "message.send_standard_quote_at_or_above_target",
        "message.send_counter_within_concession_ladder_above_target",
    }
)


@dataclass
class PolicyRequest:
    action: str
    permission_class: ToolPermissionClass
    workspace: Workspace
    opportunity_type: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    flags: frozenset[str] = (
        frozenset()
    )  # e.g. {"scam_suspected", "suspicious_injection", "low_confidence"}


@dataclass
class PolicyResult:
    decision: PolicyDecision
    reason: str


_ALWAYS_ESCALATE_FLAGS = frozenset({"scam_suspected", "suspicious_injection", "low_confidence"})


def evaluate(request: PolicyRequest) -> PolicyResult:
    """Returns ALLOW / REQUIRE_APPROVAL / DENY with a human-readable reason.

    Callers MUST persist the (request, result) pair to the audit log —
    see `app.services.audit_service.log_policy_decision`.
    """
    if request.permission_class == ToolPermissionClass.NEVER:
        return PolicyResult(PolicyDecision.DENY, "Action is not exposed to agents (NEVER class).")

    if request.permission_class in (ToolPermissionClass.READ, ToolPermissionClass.DRAFT):
        return PolicyResult(
            PolicyDecision.ALLOW, f"{request.permission_class.value} actions are always allowed."
        )

    # From here on: SIDE_EFFECT.
    if request.workspace.kill_switch:
        return PolicyResult(PolicyDecision.DENY, "Workspace kill switch is engaged.")

    if request.action in HARD_DENY_ACTIONS:
        return PolicyResult(
            PolicyDecision.DENY, f"'{request.action}' is never automated at any autonomy level."
        )

    matched_flags = request.flags & _ALWAYS_ESCALATE_FLAGS
    if matched_flags:
        return PolicyResult(
            PolicyDecision.REQUIRE_APPROVAL,
            f"Flagged {sorted(matched_flags)} — always requires human approval "
            "regardless of autonomy level.",
        )

    autonomy = request.workspace.autonomy.level_for(request.opportunity_type)

    if autonomy == AutonomyLevel.L0_DRAFT_ONLY:
        return PolicyResult(
            PolicyDecision.REQUIRE_APPROVAL, "Workspace autonomy is L0 (draft only)."
        )

    if autonomy == AutonomyLevel.L1_AUTO_SEND_LOW_STAKES:
        if request.action in L1_ALLOWED_ACTIONS:
            return PolicyResult(PolicyDecision.ALLOW, f"L1 permits '{request.action}'.")
        return PolicyResult(
            PolicyDecision.REQUIRE_APPROVAL, f"'{request.action}' is outside the L1 allow-list."
        )

    if autonomy == AutonomyLevel.L2_AUTO_NEGOTIATE_WITHIN_RAILS:
        if request.action in L1_ALLOWED_ACTIONS or request.action in L2_ADDITIONAL_ACTIONS:
            return PolicyResult(PolicyDecision.ALLOW, f"L2 permits '{request.action}'.")
        return PolicyResult(
            PolicyDecision.REQUIRE_APPROVAL, f"'{request.action}' is outside the L2 allow-list."
        )

    return PolicyResult(
        PolicyDecision.REQUIRE_APPROVAL, "Unrecognized autonomy level; defaulting safe."
    )
