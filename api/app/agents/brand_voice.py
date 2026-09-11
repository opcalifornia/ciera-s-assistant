"""Brand Voice agent (Section 4.3) — the signature feature.

Produces either a full option set (2-4 strategically distinct replies,
Section 4.3.1) or quick-reply chips for simple messages (Section 4.3.1:
"thanks, scheduling confirmations, fan mail"). `policy_status` is never
set here — Section 4.3.1 is explicit that policy status is "computed by
the Policy Engine, never by the LLM"; the router fills it in after this
agent returns.

Playbook-aware: when a Scenario Playbook matched (Section 4.3.2), its
fixed options are used as-is (with the agent filling in draft text for
each), optionally topped up with AI-generated extra options if the
playbook allows it.
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from app.agents.deal_desk import draft_reply_option
from app.agents.schemas import (
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

# Section 4.3.1: simple messages get quick-reply chips, not a full option set.
_QUICK_REPLY_CLASSES = frozenset({MessageClass.FAN_MAIL, MessageClass.PERSONAL})

# Section 11 "Never automated" + Section 4.3.1 "Needs your call": these
# never get AI-authored draft text at all, regardless of LLM output.
_NEEDS_YOUR_CALL_CLASSES = frozenset(
    {MessageClass.SCAM_SUSPECTED, MessageClass.SUSPICIOUS_INJECTION}
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
{playbook_context}
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


def _negotiation_context(negotiation: NegotiationResult | None) -> str:
    if negotiation is None or negotiation.move == NegotiationMove.NO_OFFERING_CONFIGURED:
        return ""
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


def _build_system_prompt(
    brand: Brand, playbook: ScenarioPlaybook | None, negotiation: NegotiationResult | None = None
) -> str:
    playbook_context = _negotiation_context(negotiation)
    fixed_option_note = ""
    if playbook is not None:
        fixed_labels = "; ".join(
            f'"{opt.label}" ({opt.strategy})' for opt in playbook.fixed_options
        )
        playbook_context += (
            f'\nA Scenario Playbook matched this message: "{playbook.name}". '
            f"You MUST include an option for each of these fixed moves: {fixed_labels}. "
        )
        if playbook.allow_ai_extra_options:
            playbook_context += "You may add extra strategically-distinct options beyond these.\n"
            fixed_option_note = (
                f", including the {len(playbook.fixed_options)} required fixed option(s)"
            )
        else:
            playbook_context += "Do not add any options beyond these.\n"
            fixed_option_note = " (exactly the fixed options listed above, no more)"

    return SYSTEM_PROMPT_TEMPLATE.format(
        assistant_name=brand.assistant_name,
        persona_name=brand.persona_name,
        values=", ".join(brand.values) or "(none configured)",
        no_go_categories=", ".join(brand.no_go_categories) or "(none configured)",
        playbook_context=playbook_context,
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
    ) -> OptionSetResult:
        if triage.classification in _NEEDS_YOUR_CALL_CLASSES:
            return _needs_your_call()

        if playbook is None and triage.classification in _QUICK_REPLY_CLASSES:
            return OptionSetResult(
                quick_replies=[
                    QuickReply(
                        label="Thank them",
                        draft=f"Thank you so much for the kind words! — {brand.assistant_name}, "
                        f"on behalf of {brand.persona_name}",
                        action="message.send_acknowledgment",
                    )
                ]
            )

        # Deal Desk already computed the exact numbers for opportunity-typed
        # threads with a configured rate card — that deterministic option is
        # always correct and free, so it anchors the set regardless of LLM
        # availability. The LLM, when available, only adds ADDITIONAL
        # strategically distinct options grounded on the same figures.
        grounded_option = (
            draft_reply_option(negotiation, brand)
            if negotiation is not None
            and negotiation.move != NegotiationMove.NO_OFFERING_CONFIGURED
            else None
        )

        response = await self._llm.complete(
            system=_build_system_prompt(brand, playbook, negotiation),
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
