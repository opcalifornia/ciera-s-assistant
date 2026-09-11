from app.models.opportunity import APPROVAL_GATED_STAGES, OpportunityStage, can_transition


def test_happy_path_advances_one_stage_at_a_time():
    assert can_transition(OpportunityStage.NEW, OpportunityStage.QUALIFYING)
    assert can_transition(OpportunityStage.QUALIFYING, OpportunityStage.QUOTED)
    assert can_transition(OpportunityStage.PAID, OpportunityStage.FEEDBACK_COLLECTED)


def test_cannot_skip_stages():
    assert not can_transition(OpportunityStage.NEW, OpportunityStage.QUOTED)
    assert not can_transition(OpportunityStage.QUALIFYING, OpportunityStage.CONFIRMED)


def test_cannot_go_backwards_on_happy_path():
    assert not can_transition(OpportunityStage.QUOTED, OpportunityStage.QUALIFYING)


def test_negotiation_can_loop_between_quoted_and_countering():
    assert can_transition(OpportunityStage.QUOTED, OpportunityStage.COUNTERING)
    assert can_transition(OpportunityStage.COUNTERING, OpportunityStage.QUOTED)


def test_any_non_terminal_stage_can_reach_closed_lost_or_ghosted():
    for stage in OpportunityStage:
        if stage.is_terminal:
            continue
        assert can_transition(stage, OpportunityStage.CLOSED_LOST)
        assert can_transition(stage, OpportunityStage.GHOSTED)
        assert can_transition(stage, OpportunityStage.ON_HOLD)


def test_terminal_stages_have_no_outgoing_transitions():
    for terminal in (
        OpportunityStage.CLOSED_WON,
        OpportunityStage.CLOSED_LOST,
        OpportunityStage.DECLINED_BY_TALENT,
        OpportunityStage.GHOSTED,
    ):
        assert not can_transition(terminal, OpportunityStage.QUALIFYING)
        assert not can_transition(terminal, OpportunityStage.CLOSED_LOST)


def test_verbal_yes_and_beyond_are_approval_gated():
    # Section 9.3: "Stage transitions to verbal_yes and beyond always
    # require talent approval."
    assert OpportunityStage.VERBAL_YES in APPROVAL_GATED_STAGES
    assert OpportunityStage.CONTRACTING in APPROVAL_GATED_STAGES
    assert OpportunityStage.DEPOSIT_PENDING in APPROVAL_GATED_STAGES
    assert OpportunityStage.CONFIRMED in APPROVAL_GATED_STAGES
    assert OpportunityStage.QUOTED not in APPROVAL_GATED_STAGES
