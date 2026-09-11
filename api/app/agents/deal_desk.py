"""Deal Desk — the negotiation turn algorithm (Section 9.4).

Deliberately plain, deterministic code, same spirit as the Policy
Engine (Section 2 principle 2: "the LLM proposes, deterministic code
disposes"). This module decides the NUMBERS; Brand Voice (an LLM) only
turns the decision into voice-matched prose, grounded on these exact
figures so it can't invent or leak anything — including the floor,
which never appears anywhere in `NegotiationResult`.

A final guard re-checks every quoted amount against the floor right
before returning, even though every code path above it should already
respect it — defense in depth against a future bug or a misconfigured
rate card (target set below floor by data-entry error, say).
"""

from __future__ import annotations

import re

from app.agents.schemas import NegotiationMove, NegotiationResult, ReplyOption, TriageResult
from app.models.brand import Brand
from app.models.offering import Offering
from app.services.pricing_service import (
    apply_concession,
    best_concession_for_budget,
    is_at_or_above_floor,
    is_at_or_above_target,
)

ESSENTIAL_FIELDS = frozenset({"scope", "deliverables", "date", "dates"})

# Policy Engine action ids (app/core/policy_engine.py) — REQUEST_MISSING_INFO,
# CONFIRM_SCOPE_AT_BUDGET/QUOTE_AT_ANCHOR, and COUNTER_WITH_CONCESSION map onto
# the L2 allow-list exactly; DECLINE_BELOW_FLOOR and NO_OFFERING_CONFIGURED are
# intentionally NOT on any allow-list, so they always require approval.
_MOVE_ACTIONS: dict[NegotiationMove, str] = {
    NegotiationMove.REQUEST_MISSING_INFO: "message.request_missing_info",
    NegotiationMove.CONFIRM_SCOPE_AT_BUDGET: "message.send_standard_quote_at_or_above_target",
    NegotiationMove.QUOTE_AT_ANCHOR: "message.send_standard_quote_at_or_above_target",
    NegotiationMove.COUNTER_WITH_CONCESSION: (
        "message.send_counter_within_concession_ladder_above_target"
    ),
    NegotiationMove.DECLINE_BELOW_FLOOR: "message.send_decline_below_floor",
    NegotiationMove.NO_OFFERING_CONFIGURED: "message.send_reply",
}
_BUDGET_FIELD_KEYS = ("budget", "budget_range", "offer_amount", "proposed_budget")
_NUMERIC_RE = re.compile(r"[0-9][0-9,]*(?:\.[0-9]+)?")


def _parse_budget(extracted_fields: dict[str, str]) -> float | None:
    for key in _BUDGET_FIELD_KEYS:
        raw = extracted_fields.get(key)
        if not raw:
            continue
        match = _NUMERIC_RE.search(raw)
        if match:
            try:
                return float(match.group(0).replace(",", ""))
            except ValueError:
                continue
    return None


def _decide(*, offering: Offering, triage: TriageResult) -> NegotiationResult:
    if offering.target is None or offering.floor is None:
        return NegotiationResult(
            move=NegotiationMove.NO_OFFERING_CONFIGURED,
            rationale="No target/floor configured for this offering yet — needs manual pricing.",
        )

    missing_essentials = [f for f in triage.missing_fields if f.lower() in ESSENTIAL_FIELDS]
    budget = _parse_budget(triage.extracted_fields)

    if missing_essentials and budget is None:
        return NegotiationResult(
            move=NegotiationMove.REQUEST_MISSING_INFO,
            missing_fields=missing_essentials,
            rationale=f"Missing {', '.join(missing_essentials)} before a quote makes sense.",
        )

    if budget is None:
        return NegotiationResult(
            move=NegotiationMove.QUOTE_AT_ANCHOR,
            quoted_amount=offering.anchor,
            rationale="No budget stated — quoting at anchor with the standard package.",
        )

    if is_at_or_above_target(budget, offering):
        return NegotiationResult(
            move=NegotiationMove.CONFIRM_SCOPE_AT_BUDGET,
            quoted_amount=budget,
            rationale="Stated budget already clears target — confirm scope and move forward.",
        )

    if is_at_or_above_floor(budget, offering):
        rule = best_concession_for_budget(offering, budget)
        if rule is not None:
            return NegotiationResult(
                move=NegotiationMove.COUNTER_WITH_CONCESSION,
                quoted_amount=apply_concession(offering.target, rule),
                concession_label=rule.label,
                concession_requires=rule.requires,
                rationale=f"Countering within the concession ladder: {rule.label}.",
            )
        return NegotiationResult(
            move=NegotiationMove.COUNTER_WITH_CONCESSION,
            quoted_amount=offering.target,
            rationale="Budget is below target with no matching concession — holding at target.",
        )

    return NegotiationResult(
        move=NegotiationMove.DECLINE_BELOW_FLOOR,
        rationale="Stated budget doesn't support this offering — decline or reduce scope.",
    )


def negotiate(*, offering: Offering | None, triage: TriageResult) -> NegotiationResult:
    if offering is None:
        return NegotiationResult(
            move=NegotiationMove.NO_OFFERING_CONFIGURED,
            rationale="No offering catalog entry matches this opportunity type yet.",
            action=_MOVE_ACTIONS[NegotiationMove.NO_OFFERING_CONFIGURED],
        )

    result = _decide(offering=offering, triage=triage)

    if (
        result.quoted_amount is not None
        and offering.floor is not None
        and result.quoted_amount < offering.floor
    ):
        result = NegotiationResult(
            move=NegotiationMove.DECLINE_BELOW_FLOOR,
            rationale="Computed quote fell below floor on a final safety check — declining.",
        )

    result.action = _MOVE_ACTIONS[result.move]
    return result


def _money(amount: float) -> str:
    return f"${amount:,.0f}"


def draft_reply_option(negotiation: NegotiationResult, brand: Brand) -> ReplyOption | None:
    """A correct, zero-cost, template-phrased reply straight from the
    deterministic decision — no LLM required. Not "voice-matched" the
    way a real Brand Voice draft would be once funded, but the NUMBERS
    are always right, which is the part that actually needs to be right.
    Returns None for NO_OFFERING_CONFIGURED — there's nothing safe to
    template without a rate card."""
    signature = brand.signature or f"— {brand.assistant_name}"

    if negotiation.move == NegotiationMove.REQUEST_MISSING_INFO:
        fields = ", ".join(negotiation.missing_fields) or "a few more details"
        return ReplyOption(
            label="Ask for missing info",
            strategy="Get the essentials before quoting anything.",
            tradeoff="Slower to a number, but avoids quoting blind.",
            likely_outcome="They reply with the missing details.",
            draft=f"Thanks for reaching out! Before I can put together a quote, could you "
            f"share {fields}?\n\n{signature}",
            is_recommended=True,
            recommendation_reason="Nothing to quote against yet.",
            action=negotiation.action,
        )

    if negotiation.move == NegotiationMove.QUOTE_AT_ANCHOR:
        amount = (
            _money(negotiation.quoted_amount) if negotiation.quoted_amount else "our standard rate"
        )
        return ReplyOption(
            label="Quote at standard rate",
            strategy="No budget given — anchor at the standard package price.",
            tradeoff="Sets a clear number; leaves room to negotiate down within rails.",
            likely_outcome="They confirm, counter, or ask for tiered options.",
            draft=f"Thanks for your interest! For this, our rate is {amount}. Happy to walk "
            f"through package options if useful — let me know how you'd like to proceed.\n\n"
            f"{signature}",
            is_recommended=True,
            recommendation_reason="Standard opening quote per the rate card.",
            action=negotiation.action,
        )

    if negotiation.move == NegotiationMove.CONFIRM_SCOPE_AT_BUDGET:
        amount = (
            _money(negotiation.quoted_amount) if negotiation.quoted_amount else "your stated budget"
        )
        return ReplyOption(
            label="Confirm scope",
            strategy="Budget already clears target — move straight to confirming scope.",
            tradeoff="Fast path to yes; doesn't try to extract more value.",
            likely_outcome="They confirm scope and move toward a contract.",
            draft=f"That budget works well on our end! Let's confirm the scope and details, "
            f"and I'll get things moving at {amount}.\n\n{signature}",
            is_recommended=True,
            recommendation_reason="Budget clears target — no need to counter.",
            action=negotiation.action,
        )

    if negotiation.move == NegotiationMove.COUNTER_WITH_CONCESSION:
        amount = (
            _money(negotiation.quoted_amount) if negotiation.quoted_amount else "a revised number"
        )
        ask = negotiation.concession_requires or "a small adjustment to scope"
        return ReplyOption(
            label="Counter with a trade",
            strategy="Meet closer to their budget in exchange for a concession.",
            tradeoff=f"Lower fee ({amount}) in exchange for: {ask}.",
            likely_outcome="They accept the trade or come back with a revised ask.",
            draft=f"We can make {amount} work for this, as long as we can agree on: {ask}. "
            f"Let me know if that's workable on your end.\n\n{signature}",
            is_recommended=True,
            recommendation_reason=negotiation.rationale,
            action=negotiation.action,
            numbers={"quoted_amount": amount},
        )

    if negotiation.move == NegotiationMove.DECLINE_BELOW_FLOOR:
        return ReplyOption(
            label="Decline gracefully",
            strategy="Budget doesn't support this offering — pass without revealing pricing.",
            tradeoff="Preserves the relationship; leaves the door open for a larger future budget.",
            likely_outcome="They either move on or come back with a larger budget.",
            draft="Thanks so much for thinking of us! Unfortunately this doesn't line up with "
            "our current rates for this. Happy to revisit if the budget changes, or we could "
            f"explore a reduced-scope option instead.\n\n{signature}",
            is_recommended=True,
            recommendation_reason="Budget is below what this offering supports.",
            action=negotiation.action,
        )

    return None
