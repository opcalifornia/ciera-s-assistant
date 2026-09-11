from app.models.offering import ConcessionRule, ModifierKind, Offering, RateModifier
from app.services.pricing_service import (
    apply_concession,
    apply_modifiers,
    best_concession_for_budget,
    is_at_or_above_floor,
    is_at_or_above_target,
)


def make_offering(**kwargs) -> Offering:
    defaults = dict(
        workspace_id="ws1",
        brand_id="b1",
        opportunity_type="brand_deal",
        name="Sponsored Reel",
        anchor=3000.0,
        target=2000.0,
        floor=1200.0,
    )
    defaults.update(kwargs)
    return Offering(**defaults)


def test_additive_modifier_applies_before_multiplicative():
    modifiers = [
        RateModifier(key="travel", label="Travel day", kind=ModifierKind.ADDITIVE, amount=500),
        RateModifier(
            key="virtual_discount", label="Virtual", kind=ModifierKind.MULTIPLICATIVE, amount=-0.2
        ),
    ]
    # (1000 + 500) * 0.8 = 1200
    result = apply_modifiers(1000, modifiers, {"travel", "virtual_discount"})
    assert result == 1200.0


def test_unselected_modifiers_have_no_effect():
    modifiers = [RateModifier(key="rush", label="Rush", kind=ModifierKind.ADDITIVE, amount=1000)]
    assert apply_modifiers(1000, modifiers, set()) == 1000.0


def test_apply_concession_discounts_from_base():
    rule = ConcessionRule(
        label="Shorter usage", fee_adjustment_pct=-0.15, requires="usage <= 90 days"
    )
    assert apply_concession(2000, rule) == 1700.0


def test_is_at_or_above_floor():
    offering = make_offering()
    assert is_at_or_above_floor(1200, offering)
    assert is_at_or_above_floor(1500, offering)
    assert not is_at_or_above_floor(1199.99, offering)


def test_missing_floor_is_never_treated_as_above_floor():
    offering = make_offering(floor=None)
    assert not is_at_or_above_floor(999999, offering)


def test_is_at_or_above_target():
    offering = make_offering()
    assert is_at_or_above_target(2000, offering)
    assert not is_at_or_above_target(1999.99, offering)


def test_best_concession_for_budget_never_drops_below_floor():
    offering = make_offering(
        concession_ladder=[
            ConcessionRule(
                label="Small discount", fee_adjustment_pct=-0.05, requires="add book bundle"
            ),
            ConcessionRule(
                label="Big discount", fee_adjustment_pct=-0.50, requires="drop exclusivity"
            ),
        ]
    )
    # Budget of 1900 rules out the 5% discount (1900) but the big one
    # (1000) also clears — but that's BELOW the budget check floor of the
    # budget itself; the picked concession must still clear the budget.
    rule = best_concession_for_budget(offering, budget=1900)
    assert rule is not None
    assert rule.label == "Small discount"


def test_best_concession_for_budget_returns_none_if_nothing_clears_floor():
    offering = make_offering(
        floor=1900,  # nothing in the ladder can legally reach this
        concession_ladder=[
            ConcessionRule(
                label="Big discount", fee_adjustment_pct=-0.50, requires="drop exclusivity"
            ),
        ],
    )
    assert best_concession_for_budget(offering, budget=1000) is None
