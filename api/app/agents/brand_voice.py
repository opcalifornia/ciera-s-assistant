"""Brand Voice agent (Section 4.3) — the signature feature.

Produces either a full option set (2-4 strategically distinct replies,
Section 4.3.1) or quick-reply chips for simple messages (Section 4.3.1:
"thanks, scheduling confirmations, fan mail"). `policy_status` is never
set here — Section 4.3.1 is explicit that policy status is "computed by
the Policy Engine, never by the LLM"; the router fills it in after this
agent returns.

Three deterministic "desks" can ground a reply before the LLM ever runs
— Deal Desk (priced negotiation), Bulk Desk (quantity-based book-order
pricing), and Comms Desk (everything else: fan mail, press, vendor
pitches, admin/billing, unpaid media, open-ended collaborations, spam).
Whichever applies produces a free, always-correct default option; the
LLM, when available, only adds extra strategically distinct options on
top of it, grounded on the same facts so it can't contradict them.

Playbook-aware: when a Scenario Playbook matched (Section 4.3.2), its
fixed options take precedence over Comms Desk's generic defaults (with
the agent filling in draft text for each), optionally topped up with
AI-generated extra options if the playbook allows it. A priced
negotiation or bulk quote still grounds the set even when a playbook
matched — those are facts about the deal, not a communication style.
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from app.agents import comms_desk
from app.agents.bulk_desk import draft_bulk_reply
from app.agents.comms_desk import CommsPlan
from app.agents.deal_desk import draft_reply_option
from app.agents.schemas import (
    BulkMove,
    BulkQuoteResult,
    MessageClass,
    NegotiationMove,
    NegotiationResult,
    OptionSetResult,
    QuickReply,
    ReplyOption,
    TriageResult,
)
from app.core.models_config import ModelTier
from app.models.brand import Brand
from app.models.playbook import ScenarioPlaybook
from app.providers.llm import LLMProvider

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)

# Section 11 "Never automated" + Section 4.3.1 "Needs your call": these
# never get AI-authored draft text at all, regardless of LLM output.
# Legal joins scam/injection here — Section 2 principle 5 doesn't call
# out legal explicitly, but "never automated" absolutely should: a
# drafted response to a legal matter is exactly the kind of thing that
# must never leave this system without a human reading it first.
_NEEDS_YOUR_CALL_CLASSES = frozenset(
    {MessageClass.SCAM_SUSPECTED, MessageClass.SUSPICIOUS_INJECTION, MessageClass.LEGAL}
)

SYSTEM_PROMPT_TEMPLATE = """You are the Brand Voice agent, drafting reply options for \
{assistant_name}, an AI assistant working on behalf of {persona_name} (Section 2: you are \
an AI, you sign as one, you never claim to be human).

You do not decide whether anything is allowed to send — a separate policy engine does that. \
Your job is only to draft strategically DIFFERENT options, not tone variants of the same move. \
Each option must lead to a different outcome (e.g. "counter high" vs "ask qualifying questions" \
vs "polite pass").

{persona_name}'s values: {values}
{persona_name}'s no-go categories: {no_go_categories}
{grounding_context}
Respond with ONLY a single JSON object, no other text:
{{
  "options": [
    {{
      "label": "2-4 word goal-oriented name",
      "strategy": "one sentence on what this move does",
      "tradeoff": "what it prioritizes and what it risks",
      "likely_outcome": "what the other side will probably do next",
      "draft": "the full reply, in {persona_name}'s voice, signed {signature}",
      "is_recommended": true or false (exactly one option should be true),
      "recommendation_reason": "one line, only on the recommended option, else empty string"
    }}
  ]
}}
Produce 2 to 4 options total{fixed_option_note}.
"""


def _negotiation_context(negotiation: NegotiationResult) -> str:
    lines = [
        "\nThe Deal Desk has already computed the numbers for this reply — use these EXACT "
        "figures in every option that quotes a price. Never invent a different number, and "
        "never state or imply a floor/walk-away price.",
        f"Decision: {negotiation.move.value}",
    ]
    if negotiation.quoted_amount is not None:
        lines.append(f"Amount to quote: ${negotiation.quoted_amount:,.0f}")
    if negotiation.concession_requires:
        lines.append(
            f"If offering this price, it must be paired with this trade: "
            f"{negotiation.concession_requires}"
        )
    if negotiation.missing_fields:
        lines.append(f"Missing info to ask for: {', '.join(negotiation.missing_fields)}")
    return "\n".join(lines) + "\n"


def _bulk_context(bulk: BulkQuoteResult) -> str:
    lines = [
        "\nThe Bulk Desk has already computed the numbers for this order — use these EXACT "
        "figures, never invent different ones.",
        f"Decision: {bulk.move.value}",
    ]
    if bulk.quantity is not None:
        lines.append(f"Quantity: {bulk.quantity}")
    if bulk.total_amount is not None:
        lines.append(
            f"Total to quote: ${bulk.total_amount:,.2f} (${bulk.unit_price:,.2f}/unit, "
            f"{bulk.tier_label})"
        )
    return "\n".join(lines) + "\n"


def _comms_context(comms_plan: CommsPlan) -> str:
    opt = comms_plan.option_set.options[0]
    return (
        f'\nA default plan already exists for this message: "{opt.label}" — {opt.strategy} '
        "Ground any extra options around getting the same missing information; don't invent "
        "numbers or commitments.\n"
    )


def _grounding_context(
    negotiation: NegotiationResult | None,
    bulk: BulkQuoteResult | None,
    comms_plan: CommsPlan | None,
) -> str:
    if negotiation is not None and negotiation.move != NegotiationMove.NO_OFFERING_CONFIGURED:
        return _negotiation_context(negotiation)
    if bulk is not None and bulk.move != BulkMove.NO_TIERS_CONFIGURED:
        return _bulk_context(bulk)
    if comms_plan is not None and comms_plan.option_set.options:
        return _comms_context(comms_plan)
    return ""


def _build_system_prompt(
    brand: Brand,
    playbook: ScenarioPlaybook | None,
    negotiation: NegotiationResult | None,
    bulk: BulkQuoteResult | None,
    comms_plan: CommsPlan | None,
) -> str:
    grounding_context = _grounding_context(negotiation, bulk, comms_plan)
    fixed_option_note = ""
    if playbook is not None:
        fixed_labels = "; ".join(
            f'"{opt.label}" ({opt.strategy})' for opt in playbook.fixed_options
        )
        grounding_context += (
            f'\nA Scenario Playbook matched this message: "{playbook.name}". '
            f"You MUST include an option for each of these fixed moves: {fixed_labels}. "
        )
        if playbook.allow_ai_extra_options:
            grounding_context += "You may add extra strategically-distinct options beyond these.\n"
            fixed_option_note = (
                f", including the {len(playbook.fixed_options)} required fixed option(s)"
            )
        else:
            grounding_context += "Do not add any options beyond these.\n"
            fixed_option_note = " (exactly the fixed options listed above, no more)"

    return SYSTEM_PROMPT_TEMPLATE.format(
        assistant_name=brand.assistant_name,
        persona_name=brand.persona_name,
        values=", ".join(brand.values) or "(none configured)",
        no_go_categories=", ".join(brand.no_go_categories) or "(none configured)",
        grounding_context=grounding_context,
        signature=brand.signature or f"— {brand.assistant_name}",
        fixed_option_note=fixed_option_note,
    )


def _parse_options(response_text: str) -> list[ReplyOption] | None:
    match = _JSON_BLOCK.search(response_text)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict) or "options" not in parsed:
        return None
    try:
        options = [ReplyOption.model_validate(opt) for opt in parsed["options"]]
    except ValidationError:
        return None
    if not options:
        return None
    # Guarantee exactly one recommended option.
    if not any(opt.is_recommended for opt in options):
        options[0].is_recommended = True
    return options


def _fallback_quick_reply() -> OptionSetResult:
    return OptionSetResult(
        quick_replies=[
            QuickReply(
                label="Review manually",
                draft="",
                action="message.review_manually",
            )
        ],
    )


def _needs_your_call() -> OptionSetResult:
    return OptionSetResult(
        quick_replies=[
            QuickReply(label="Needs your call", draft="", action="message.escalate_to_talent")
        ],
    )


class BrandVoiceAgent:
    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def run(
        self,
        *,
        brand: Brand,
        triage: TriageResult,
        sender: str,
        subject: str,
        body: str,
        workspace_id: str,
        playbook: ScenarioPlaybook | None = None,
        negotiation: NegotiationResult | None = None,
        bulk: BulkQuoteResult | None = None,
    ) -> OptionSetResult:
        if triage.classification in _NEEDS_YOUR_CALL_CLASSES:
            return _needs_your_call()

        # Comms Desk's generic defaults only apply when no Scenario
        # Playbook matched — a playbook the talent configured always wins
        # over a built-in default (Section 4.3.2).
        comms_plan: CommsPlan | None = None
        if playbook is None:
            comms_plan = comms_desk.plan_response(triage, brand)
            if comms_plan is not None and not comms_plan.allow_llm_topup:
                return comms_plan.option_set

        # Whichever deterministic desk applies anchors the option set —
        # always correct and free, so it's there regardless of LLM
        # availability. The LLM, when available, only adds ADDITIONAL
        # strategically distinct options grounded on the same facts.
        grounded_option: ReplyOption | None = None
        if negotiation is not None and negotiation.move != NegotiationMove.NO_OFFERING_CONFIGURED:
            grounded_option = draft_reply_option(negotiation, brand)
        elif bulk is not None and bulk.move != BulkMove.NO_TIERS_CONFIGURED:
            grounded_option = draft_bulk_reply(bulk, brand)
        elif comms_plan is not None and comms_plan.option_set.options:
            grounded_option = comms_plan.option_set.options[0]

        response = await self._llm.complete(
            system=_build_system_prompt(brand, playbook, negotiation, bulk, comms_plan),
            messages=[{"role": "user", "content": f"From: {sender}\nSubject: {subject}\n\n{body}"}],
            tier=ModelTier.BALANCED,
            workspace_id=workspace_id,
        )

        llm_options = _parse_options(response.text)

        if llm_options is None:
            if grounded_option is not None:
                return OptionSetResult(
                    options=[grounded_option], playbook_id=str(playbook.id) if playbook else None
                )
            return _fallback_quick_reply()

        if grounded_option is not None:
            # The grounded option is the source of truth for numbers/action;
            # keep it recommended, demote any LLM options that duplicate its
            # label, and cap the total at 4 (Section 4.3.1).
            for opt in llm_options:
                opt.is_recommended = False
            extra = [o for o in llm_options if o.label != grounded_option.label][:3]
            combined = [grounded_option, *extra]
            return OptionSetResult(
                options=combined, playbook_id=str(playbook.id) if playbook else None
            )

        return OptionSetResult(
            options=llm_options, playbook_id=str(playbook.id) if playbook else None
        )
