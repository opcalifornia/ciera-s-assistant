from app.agents.deal_desk import negotiate
from app.agents.schemas import MessageClass, NegotiationMove, TriageResult
from app.models.offering import ConcessionRule, Offering


def make_offering(**kwargs) -> Offering:
    defaults = dict(
        workspace_id="ws1",
        brand_id="b1",
        opportunity_type="brand_deal",
        name="Sponsored Reel",
        anchor=3000.0,
        target=2000.0,
        floor=1200.0,
        concession_ladder=[
            ConcessionRule(
                label="Shorter usage window", fee_adjustment_pct=-0.10, requires="usage <= 90 days"
            ),
            ConcessionRule(
                label="Drop exclusivity",
                fee_adjustment_pct=-0.35,
                requires="no category exclusivity",
            ),
        ],
    )
    defaults.update(kwargs)
    return Offering(**defaults)


def make_triage(**kwargs) -> TriageResult:
    defaults = dict(classification=MessageClass.BRAND_DEAL, summary="s")
    defaults.update(kwargs)
    return TriageResult(**defaults)


def test_no_offering_never_invents_a_quote():
    result = negotiate(offering=None, triage=make_triage())
    assert result.move == NegotiationMove.NO_OFFERING_CONFIGURED
    assert result.quoted_amount is None


def test_offering_without_target_or_floor_refuses_to_negotiate():
    offering = make_offering(target=None, floor=None)
    result = negotiate(offering=offering, triage=make_triage())
    assert result.move == NegotiationMove.NO_OFFERING_CONFIGURED


def test_missing_essential_fields_requests_info_before_quoting():
    triage = make_triage(missing_fields=["scope", "date"])
    result = negotiate(offering=make_offering(), triage=triage)
    assert result.move == NegotiationMove.REQUEST_MISSING_INFO
    assert result.quoted_amount is None
    assert set(result.missing_fields) == {"scope", "date"}


def test_no_budget_quotes_at_anchor():
    result = negotiate(offering=make_offering(), triage=make_triage())
    assert result.move == NegotiationMove.QUOTE_AT_ANCHOR
    assert result.quoted_amount == 3000.0


def test_budget_at_or_above_target_confirms_scope():
    triage = make_triage(extracted_fields={"budget": "$2,500"})
    result = negotiate(offering=make_offering(), triage=triage)
    assert result.move == NegotiationMove.CONFIRM_SCOPE_AT_BUDGET
    assert result.quoted_amount == 2500.0


def test_budget_between_floor_and_target_counters_with_smallest_sufficient_concession():
    # Budget of $1,850 is high enough that the smaller 10% discount
    # (-> $1,800) already clears it, so that's the one that should be
    # picked over the bigger 35% discount — least concession necessary.
    triage = make_triage(extracted_fields={"budget": "$1,850"})
    result = negotiate(offering=make_offering(), triage=triage)
    assert result.move == NegotiationMove.COUNTER_WITH_CONCESSION
    assert result.concession_label == "Shorter usage window"
    assert result.concession_requires == "usage <= 90 days"
    assert result.quoted_amount == 1800.0  # 2000 * 0.9
    assert result.quoted_amount >= 1200.0  # never below floor


def test_budget_requires_the_bigger_concession_when_the_smaller_one_does_not_clear_it():
    # Budget of $1,700 is below what the 10% discount ($1,800) clears, so
    # the engine must reach for the bigger 35% discount ($1,300) instead.
    triage = make_triage(extracted_fields={"budget": "$1,700"})
    result = negotiate(offering=make_offering(), triage=triage)
    assert result.move == NegotiationMove.COUNTER_WITH_CONCESSION
    assert result.concession_label == "Drop exclusivity"
    assert result.quoted_amount == 1300.0
    assert result.quoted_amount >= 1200.0


def test_budget_below_floor_declines_and_never_reveals_the_number():
    triage = make_triage(extracted_fields={"budget": "$500"})
    result = negotiate(offering=make_offering(), triage=triage)
    assert result.move == NegotiationMove.DECLINE_BELOW_FLOOR
    assert result.quoted_amount is None
    assert "1200" not in result.rationale
    assert "floor" not in result.rationale.lower() or "1200" not in result.rationale


def test_concession_ladder_never_produces_a_quote_below_floor_even_if_misconfigured():
    # Pathological rate card: a concession that would legally undercut the
    # floor if the ladder logic didn't clamp it (pricing_service already
    # excludes it, but this proves the final guard in negotiate() too).
    offering = make_offering(
        target=2000.0,
        floor=1990.0,
        concession_ladder=[
            ConcessionRule(
                label="Huge discount", fee_adjustment_pct=-0.9, requires="give up everything"
            ),
        ],
    )
    triage = make_triage(extracted_fields={"budget": "$1995"})
    result = negotiate(offering=offering, triage=triage)
    # best_concession_for_budget correctly finds nothing usable, so this
    # falls through to holding at target — never the floor-violating 200.
    assert result.quoted_amount is None or result.quoted_amount >= offering.floor


def test_no_concession_matches_holds_at_target():
    offering = make_offering(concession_ladder=[])
    triage = make_triage(extracted_fields={"budget": "$1700"})
    result = negotiate(offering=offering, triage=triage)
    assert result.move == NegotiationMove.COUNTER_WITH_CONCESSION
    assert result.quoted_amount == 2000.0
    assert result.concession_label is None
