"""Bulk Desk — quantity-based pricing for `book_order` (Section 9.1:
"bulk tier pricing"), deliberately separate from Deal Desk's
anchor/target/floor negotiation. There's no haggling here: a school or
store asks for a quantity, and the price per unit drops at configured
breakpoints. Same philosophy as `deal_desk.py` — plain code computes the
real number for free; an LLM only phrases it.
"""

from __future__ import annotations

import re

from app.agents.schemas import BulkMove, BulkQuoteResult, ReplyOption
from app.models.brand import Brand
from app.models.offering import BulkTier, Offering

_QUANTITY_RE = re.compile(
    r"(?:quantity|qty)[^0-9]{0,10}([0-9][0-9,]*)"
    r"|([0-9][0-9,]*)\s*(?:copies|books|units)"
    r"|order(?:ing)?\s+([0-9][0-9,]*)",
    re.IGNORECASE,
)


def parse_quantity(text: str) -> int | None:
    match = _QUANTITY_RE.search(text)
    if not match:
        return None
    raw = next(g for g in match.groups() if g is not None)
    try:
        return int(raw.replace(",", ""))
    except ValueError:
        return None


def _best_tier(tiers: list[BulkTier], quantity: int) -> BulkTier | None:
    eligible = [t for t in tiers if quantity >= t.min_qty]
    if not eligible:
        return None
    return max(eligible, key=lambda t: t.min_qty)


def quote_bulk(*, offering: Offering | None, quantity: int | None) -> BulkQuoteResult:
    if offering is None or not offering.bulk_tiers:
        return BulkQuoteResult(
            move=BulkMove.NO_TIERS_CONFIGURED,
            rationale="No bulk pricing tiers configured for book orders yet.",
            action="message.send_reply",
        )
    if quantity is None:
        return BulkQuoteResult(
            move=BulkMove.REQUEST_QUANTITY,
            rationale="No quantity mentioned yet — ask before quoting.",
            action="message.request_missing_info",
        )

    tier = _best_tier(offering.bulk_tiers, quantity)
    if tier is None:
        # Quantity is below every configured tier's minimum — quote the
        # lowest tier's per-unit price rather than refusing outright.
        tier = min(offering.bulk_tiers, key=lambda t: t.min_qty)

    total = round(tier.unit_price * quantity, 2)
    return BulkQuoteResult(
        move=BulkMove.QUOTE_BULK,
        quantity=quantity,
        unit_price=tier.unit_price,
        total_amount=total,
        tier_label=tier.label or f"{tier.min_qty}+ units",
        rationale=f"Quantity {quantity} matches the '{tier.label or tier.min_qty}' tier.",
        action="message.send_standard_quote_at_or_above_target",
    )


def draft_bulk_reply(result: BulkQuoteResult, brand: Brand) -> ReplyOption | None:
    sig = brand.signature or f"— {brand.assistant_name}"

    if result.move == BulkMove.REQUEST_QUANTITY:
        return ReplyOption(
            label="Ask for quantity",
            strategy="Get a firm quantity before quoting bulk pricing.",
            tradeoff="One extra round-trip, but avoids quoting the wrong tier.",
            likely_outcome="They reply with a number, which unlocks an exact quote.",
            draft=f"Happy to help with a bulk order! How many copies are you looking for?\n\n{sig}",
            is_recommended=True,
            recommendation_reason="No quantity mentioned yet.",
            action=result.action,
        )

    if result.move == BulkMove.QUOTE_BULK and result.total_amount is not None:
        return ReplyOption(
            label="Send bulk quote",
            strategy=f"Quote the '{result.tier_label}' tier at ${result.unit_price:,.2f}/unit.",
            tradeoff="Clear, fast quote; doesn't leave room to negotiate per-unit price further.",
            likely_outcome="They confirm the order or ask about shipping/timing next.",
            draft=f"For {result.quantity} copies, that comes to ${result.unit_price:,.2f} per "
            f"copy — ${result.total_amount:,.2f} total ({result.tier_label} pricing). Let me "
            f"know if you'd like to move forward!\n\n{sig}",
            is_recommended=True,
            recommendation_reason=result.rationale,
            action=result.action,
            numbers={"quantity": str(result.quantity), "total": f"${result.total_amount:,.2f}"},
        )

    return None
