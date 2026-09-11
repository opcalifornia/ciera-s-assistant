from app.core.policy_engine import (
    HARD_DENY_ACTIONS,
    PolicyDecision,
    PolicyRequest,
    ToolPermissionClass,
    evaluate,
)
from app.models.workspace import AutonomyConfig, AutonomyLevel, Workspace


def make_workspace(
    *, kill_switch: bool = False, autonomy: AutonomyLevel = AutonomyLevel.L0_DRAFT_ONLY
) -> Workspace:
    return Workspace(
        name="Test", kill_switch=kill_switch, autonomy=AutonomyConfig(default=autonomy)
    )


def test_read_actions_always_allowed():
    ws = make_workspace()
    result = evaluate(
        PolicyRequest(action="thread.read", permission_class=ToolPermissionClass.READ, workspace=ws)
    )
    assert result.decision == PolicyDecision.ALLOW


def test_draft_actions_always_allowed():
    ws = make_workspace()
    result = evaluate(
        PolicyRequest(
            action="draft.create", permission_class=ToolPermissionClass.DRAFT, workspace=ws
        )
    )
    assert result.decision == PolicyDecision.ALLOW


def test_never_class_always_denied_even_at_max_autonomy():
    ws = make_workspace(autonomy=AutonomyLevel.L2_AUTO_NEGOTIATE_WITHIN_RAILS)
    result = evaluate(
        PolicyRequest(
            action="contract.sign", permission_class=ToolPermissionClass.NEVER, workspace=ws
        )
    )
    assert result.decision == PolicyDecision.DENY


def test_hard_deny_actions_denied_regardless_of_autonomy():
    ws = make_workspace(autonomy=AutonomyLevel.L2_AUTO_NEGOTIATE_WITHIN_RAILS)
    for action in HARD_DENY_ACTIONS:
        result = evaluate(
            PolicyRequest(
                action=action, permission_class=ToolPermissionClass.SIDE_EFFECT, workspace=ws
            )
        )
        assert result.decision == PolicyDecision.DENY, action


def test_kill_switch_denies_all_side_effects():
    ws = make_workspace(kill_switch=True, autonomy=AutonomyLevel.L2_AUTO_NEGOTIATE_WITHIN_RAILS)
    result = evaluate(
        PolicyRequest(
            action="message.send_acknowledgment",
            permission_class=ToolPermissionClass.SIDE_EFFECT,
            workspace=ws,
        )
    )
    assert result.decision == PolicyDecision.DENY
    assert "kill switch" in result.reason.lower()


def test_l0_requires_approval_for_every_side_effect():
    ws = make_workspace(autonomy=AutonomyLevel.L0_DRAFT_ONLY)
    result = evaluate(
        PolicyRequest(
            action="message.send_acknowledgment",
            permission_class=ToolPermissionClass.SIDE_EFFECT,
            workspace=ws,
        )
    )
    assert result.decision == PolicyDecision.REQUIRE_APPROVAL


def test_l1_allows_low_stakes_but_not_arbitrary_actions():
    ws = make_workspace(autonomy=AutonomyLevel.L1_AUTO_SEND_LOW_STAKES)
    allowed = evaluate(
        PolicyRequest(
            action="message.send_acknowledgment",
            permission_class=ToolPermissionClass.SIDE_EFFECT,
            workspace=ws,
        )
    )
    assert allowed.decision == PolicyDecision.ALLOW

    not_allowed = evaluate(
        PolicyRequest(
            action="message.send_counter_within_concession_ladder_above_target",
            permission_class=ToolPermissionClass.SIDE_EFFECT,
            workspace=ws,
        )
    )
    assert not_allowed.decision == PolicyDecision.REQUIRE_APPROVAL


def test_l2_allows_negotiation_within_rails():
    ws = make_workspace(autonomy=AutonomyLevel.L2_AUTO_NEGOTIATE_WITHIN_RAILS)
    result = evaluate(
        PolicyRequest(
            action="message.send_counter_within_concession_ladder_above_target",
            permission_class=ToolPermissionClass.SIDE_EFFECT,
            workspace=ws,
        )
    )
    assert result.decision == PolicyDecision.ALLOW


def test_scam_flag_always_escalates_even_at_l2():
    ws = make_workspace(autonomy=AutonomyLevel.L2_AUTO_NEGOTIATE_WITHIN_RAILS)
    result = evaluate(
        PolicyRequest(
            action="message.send_acknowledgment",
            permission_class=ToolPermissionClass.SIDE_EFFECT,
            workspace=ws,
            flags=frozenset({"scam_suspected"}),
        )
    )
    assert result.decision == PolicyDecision.REQUIRE_APPROVAL


def test_suspicious_injection_flag_always_escalates():
    ws = make_workspace(autonomy=AutonomyLevel.L1_AUTO_SEND_LOW_STAKES)
    result = evaluate(
        PolicyRequest(
            action="message.send_acknowledgment",
            permission_class=ToolPermissionClass.SIDE_EFFECT,
            workspace=ws,
            flags=frozenset({"suspicious_injection"}),
        )
    )
    assert result.decision == PolicyDecision.REQUIRE_APPROVAL


def test_opportunity_type_autonomy_override():
    ws = make_workspace(autonomy=AutonomyLevel.L0_DRAFT_ONLY)
    ws.autonomy.by_opportunity_type["brand_deal"] = AutonomyLevel.L1_AUTO_SEND_LOW_STAKES
    result = evaluate(
        PolicyRequest(
            action="message.send_acknowledgment",
            permission_class=ToolPermissionClass.SIDE_EFFECT,
            workspace=ws,
            opportunity_type="brand_deal",
        )
    )
    assert result.decision == PolicyDecision.ALLOW

    result_default = evaluate(
        PolicyRequest(
            action="message.send_acknowledgment",
            permission_class=ToolPermissionClass.SIDE_EFFECT,
            workspace=ws,
            opportunity_type="speaking",
        )
    )
    assert result_default.decision == PolicyDecision.REQUIRE_APPROVAL
