"""Deterministic pricing math (Section 9.1, 9.2). Plain code — the
negotiation agent decides WHICH modifiers/concessions apply from the
conversation, but the arithmetic itself is never left to the LLM.
"""

from __future__ import annotations

from app.models.offering import ConcessionRule, ModifierKind, Offering, RateModifier


def apply_modifiers(base: float, modifiers: list[RateModifier], selected_keys: set[str]) -> float:
    """Additive modifiers apply first (against the base), then
    multiplicative ones compound on the running total — so a flat travel
    surcharge is added before a virtual-format discount takes a
    percentage off the whole package, not just the base fee."""
    amount = base
    for m in modifiers:
        if m.key in selected_keys and m.kind == ModifierKind.ADDITIVE:
            amount += m.amount
    for m in modifiers:
        if m.key in selected_keys and m.kind == ModifierKind.MULTIPLICATIVE:
            amount *= 1 + m.amount
    return round(amount, 2)


def apply_concession(base: float, rule: ConcessionRule) -> float:
    return round(base * (1 + rule.fee_adjustment_pct), 2)


def is_at_or_above_floor(amount: float, offering: Offering) -> bool:
    """Section 2 principle 5 / Section 9.5: never accept below floor.
    A missing floor is treated as "no floor configured" — callers should
    treat that as its own guardrail failure (the offering isn't ready to
    negotiate), not as "anything goes"."""
    if offering.floor is None:
        return False
    return amount >= offering.floor


def is_at_or_above_target(amount: float, offering: Offering) -> bool:
    if offering.target is None:
        return False
    return amount >= offering.target


def best_concession_for_budget(offering: Offering, budget: float) -> ConcessionRule | None:
    """Section 9.4 step 3: given a budget between floor and target, find
    the smallest concession (least fee reduction) that still clears the
    budget without dropping below floor. Returns None if no concession
    in the ladder gets there without crossing the floor."""
    if offering.target is None or offering.floor is None:
        return None
    candidates = []
    for rule in offering.concession_ladder:
        adjusted = apply_concession(offering.target, rule)
        if adjusted >= offering.floor and adjusted <= budget:
            candidates.append((adjusted, rule))
    if not candidates:
        return None
    # Smallest discount that still clears the budget (closest to target).
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return candidates[0][1]
