"""Comms Desk — deterministic reply planning for everything that ISN'T a
priced negotiation (Section 3's non-`brand_deal`-shaped classes: fan
mail, press, vendor pitches, admin/billing, unpaid media, open-ended
collaborations, spam).

Same philosophy as `deal_desk.py`: plain code decides the default move
and drafts a correct, zero-cost reply — an LLM only adds extra
strategically distinct options on top, and only where that's likely to
help (never for a one-tap "thank them" chip). This exists because
Ciera's Assistant is a front office for the whole business, not just a
deal-closing bot — most of what arrives in a working creator's inbox
is not a negotiation at all, and it deserves a real answer too.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.schemas import MessageClass, OptionSetResult, QuickReply, ReplyOption, TriageResult
from app.models.brand import Brand


@dataclass
class CommsPlan:
    option_set: OptionSetResult
    # Whether it's worth spending an LLM call to add more strategic
    # options on top of this plan. False for one-tap chips and for
    # plans that are already a complete strategic set (press inquiries).
    allow_llm_topup: bool = True


def _sig(brand: Brand) -> str:
    return brand.signature or f"— {brand.assistant_name}"


def _fan_mail(brand: Brand) -> CommsPlan:
    return CommsPlan(
        option_set=OptionSetResult(
            quick_replies=[
                QuickReply(
                    label="Thank them",
                    draft=f"Thank you so much for the kind words — it means a lot!\n\n"
                    f"{_sig(brand)}",
                    action="message.send_acknowledgment",
                )
            ]
        ),
        allow_llm_topup=False,
    )


def _personal(brand: Brand) -> CommsPlan:
    return CommsPlan(
        option_set=OptionSetResult(
            quick_replies=[
                QuickReply(
                    label="Acknowledge",
                    draft=f"Thanks for reaching out — got your message and will follow up "
                    f"personally soon.\n\n{_sig(brand)}",
                    action="message.send_acknowledgment",
                )
            ]
        ),
        allow_llm_topup=False,
    )


def _vendor_pitch(brand: Brand) -> CommsPlan:
    return CommsPlan(
        option_set=OptionSetResult(
            quick_replies=[
                QuickReply(
                    label="Decline politely",
                    draft="Thanks for thinking of us, but this isn't a fit right now. "
                    f"Appreciate you reaching out.\n\n{_sig(brand)}",
                    action="message.send_decline_spam",
                )
            ]
        ),
        allow_llm_topup=False,
    )


def _admin_billing(brand: Brand) -> CommsPlan:
    return CommsPlan(
        option_set=OptionSetResult(
            quick_replies=[
                QuickReply(
                    label="Acknowledge receipt",
                    draft=f"Got this, thank you — will take a look and follow up if anything is "
                    f"needed.\n\n{_sig(brand)}",
                    action="message.send_acknowledgment",
                )
            ]
        ),
        allow_llm_topup=False,
    )


def _press_inquiry(brand: Brand) -> CommsPlan:
    """A genuine 3-way strategic decision (Section 4.3.2's press default
    playbook), so it gets a full option set — no LLM required to make it
    real and useful."""
    sig = _sig(brand)
    options = [
        ReplyOption(
            label="Accept with conditions",
            strategy="Say yes, but set terms up front (questions in advance, review before "
            "publish).",
            tradeoff="Keeps control over the framing; a few outlets will decline the conditions.",
            likely_outcome="They agree to the conditions, or come back with a compromise.",
            draft="Happy to do this! Could you send over the questions or topics in advance, and "
            f"confirm whether we'd get to review quotes before publish?\n\n{sig}",
            is_recommended=True,
            recommendation_reason="Protects against being misquoted without over-restricting "
            "access.",
            action="message.send_acknowledgment",
        ),
        ReplyOption(
            label="Ask for more context",
            strategy="Get outlet, audience, and angle before committing either way.",
            tradeoff="Slower to a yes/no, but avoids a bad-fit interview.",
            likely_outcome="They share more detail, which makes the real decision easier.",
            draft="Thanks for reaching out! Could you share a bit more — which outlet this is "
            f"for, expected audience, and the angle you're going for?\n\n{sig}",
            action="message.send_acknowledgment",
        ),
        ReplyOption(
            label="Decline",
            strategy="Pass on this one.",
            tradeoff="Clean and fast, but closes the door on this specific opportunity.",
            likely_outcome="They may follow up once, then move on.",
            draft="Thanks so much for thinking of us — going to pass on this one, but "
            f"appreciate you reaching out.\n\n{sig}",
            action="message.send_decline_spam",
        ),
    ]
    return CommsPlan(option_set=OptionSetResult(options=options), allow_llm_topup=False)


def _unpaid_media(brand: Brand) -> CommsPlan:
    """Section 9.2: unpaid only clears if reach/strategic value clears a
    threshold — so the default move is to ask, never to accept blind."""
    sig = _sig(brand)
    return CommsPlan(
        option_set=OptionSetResult(
            options=[
                ReplyOption(
                    label="Ask about reach & terms",
                    strategy="Get audience size and promotional terms before deciding on an "
                    "unpaid ask.",
                    tradeoff="One extra round-trip, but avoids trading time for low-reach "
                    "exposure.",
                    likely_outcome="They share numbers, which is what the accept/decline call "
                    "should hinge on.",
                    draft="Thanks for the invite! Could you share your typical audience "
                    "size/reach, and whether there's promotion or a clip we'd be able to use "
                    "afterward?\n\n" + sig,
                    is_recommended=True,
                    recommendation_reason="No reach numbers yet — Section 9.2 says qualify "
                    "unpaid asks before accepting.",
                    action="message.request_missing_info",
                )
            ]
        ),
        allow_llm_topup=True,
    )


def _collaboration(brand: Brand) -> CommsPlan:
    sig = _sig(brand)
    return CommsPlan(
        option_set=OptionSetResult(
            options=[
                ReplyOption(
                    label="Ask for scope & split",
                    strategy="Get concrete scope and revenue/credit split before committing.",
                    tradeoff="Slower to a yes, but collaborations go wrong most often on vague "
                    "terms.",
                    likely_outcome="They come back with specifics, or lose interest if it was "
                    "never concrete.",
                    draft="Love the idea of collaborating! To figure out if this makes sense, "
                    "could you share what you're picturing for scope, timeline, and how revenue "
                    f"or credit would be split?\n\n{sig}",
                    is_recommended=True,
                    recommendation_reason="No scope or split mentioned yet.",
                    action="message.request_missing_info",
                )
            ]
        ),
        allow_llm_topup=True,
    )


def _spam() -> CommsPlan:
    return CommsPlan(
        option_set=OptionSetResult(
            quick_replies=[
                QuickReply(label="No action needed", draft="", action="message.no_action")
            ]
        ),
        allow_llm_topup=False,
    )


# Classes with a fixed plan that only needs the brand (signature, name).
_BRAND_ONLY_PLANS = {
    MessageClass.FAN_MAIL: _fan_mail,
    MessageClass.PERSONAL: _personal,
    MessageClass.VENDOR_PITCH: _vendor_pitch,
    MessageClass.ADMIN_BILLING: _admin_billing,
    MessageClass.PRESS_INQUIRY: _press_inquiry,
    MessageClass.MEDIA: _unpaid_media,
    MessageClass.COLLABORATION: _collaboration,
}


def plan_response(triage: TriageResult, brand: Brand) -> CommsPlan | None:
    """Returns None when Comms Desk has no opinion — the message is
    either a priced negotiation (Deal Desk's job) or something with no
    default plan at all (falls through to plain Brand Voice drafting)."""
    if triage.classification == MessageClass.SPAM:
        return _spam()

    handler = _BRAND_ONLY_PLANS.get(triage.classification)
    if handler is not None:
        return handler(brand)

    return None
