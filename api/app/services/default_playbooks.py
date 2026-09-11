"""~15 default Scenario Playbooks (Section 4.3.2, Phase 1 acceptance
criterion: "ship with ~15 default playbooks covering common scenarios
across all opportunity types"). Installed per-brand, idempotent by name.
"""

from app.models.playbook import CompiledCriteria, FixedOption, ScenarioPlaybook


def _spec(
    name: str,
    trigger: str,
    *,
    keywords: list[str] | None = None,
    sender_domains: list[str] | None = None,
    opportunity_types: list[str] | None = None,
    options: list[tuple[str, str]],
    allow_ai_extra_options: bool = True,
    priority: str = "normal",
) -> dict:
    return {
        "name": name,
        "natural_language_trigger": trigger,
        "compiled_criteria": CompiledCriteria(
            keywords=keywords or [],
            sender_domains=sender_domains or [],
            opportunity_types=opportunity_types or [],
        ),
        "fixed_options": [
            FixedOption(label=label, strategy=strategy) for label, strategy in options
        ],
        "allow_ai_extra_options": allow_ai_extra_options,
        "notification_priority": priority,
        "is_default": True,
    }


DEFAULT_PLAYBOOK_SPECS: list[dict] = [
    _spec(
        "Someone asks for my rate",
        "When someone asks for my rate",
        keywords=["rate", "pricing", "how much", "your fee", "cost to book"],
        options=[
            ("Send rate card", "Share standard pricing for the relevant offering."),
            ("Ask budget first", "Find out their budget before anchoring a number."),
            ("Send tiered packages", "Offer 2-3 packages at different price points."),
        ],
    ),
    _spec(
        "Unpaid podcast invite",
        "When a podcast invites me unpaid",
        keywords=["podcast", "no budget", "unpaid", "exposure"],
        opportunity_types=["media"],
        options=[
            ("Accept", "Take the unpaid opportunity as-is."),
            ("Accept if they promote the book", "Trade appearance for a promotional commitment."),
            ("Decline kindly", "Pass, citing bandwidth."),
        ],
    ),
    _spec(
        "School has no budget",
        "When a school says they have no budget",
        keywords=["no budget", "limited budget", "can't afford", "grant funding"],
        opportunity_types=["school_visit"],
        options=[
            ("Offer funding-path help", "Share the funding helper (Title IV-A, PTA, etc.)."),
            ("Offer virtual visit", "Propose a lower-cost virtual format."),
            ("Offer book-bundle package", "Reduce the fee in exchange for a book order."),
            ("Pass", "Decline for now."),
        ],
    ),
    _spec(
        "Usage rights or whitelisting mentioned",
        "When a brand mentions usage rights or whitelisting",
        keywords=["usage rights", "whitelisting", "whitelist", "perpetual", "paid media"],
        opportunity_types=["brand_deal"],
        options=[
            ("Flag and clarify scope", "Ask them to specify duration/territory before proceeding."),
            ("Counter with limited usage", "Offer a bounded usage window instead."),
            ("Decline the grant", "Pass if broad rights are non-negotiable for them."),
        ],
        priority="high",
    ),
    _spec(
        "Availability / date request",
        "When someone asks about availability or specific dates",
        keywords=["available", "availability", "what dates", "open dates"],
        options=[
            ("Share general availability", "Give a high-level window without confirming a hold."),
            ("Ask for their specific date", "Get a concrete date before checking the calendar."),
        ],
    ),
    _spec(
        "Fan mail",
        "When a fan sends a kind message with no ask",
        keywords=["huge fan", "big fan", "love your work", "inspired me", "changed my life"],
        options=[("Thank them warmly", "Short, genuine thank-you, no CTA needed.")],
        allow_ai_extra_options=False,
        priority="low",
    ),
    _spec(
        "Press interview request",
        "When press or a journalist asks for an interview",
        keywords=["journalist", "reporter", "press inquiry", "interview request", "on the record"],
        options=[
            ("Accept with conditions", "Agree, but request questions in advance."),
            ("Request more context", "Ask what outlet/angle before committing."),
            ("Decline", "Pass on this one."),
        ],
    ),
    _spec(
        "Vendor pitch",
        "When a vendor pitches a product or service (not a booking)",
        keywords=["free trial", "our platform", "partner with", "sponsor your channel"],
        options=[
            ("Decline", "Not a fit — politely pass."),
            ("Redirect to intake page", "Point them to the general contact form."),
        ],
        allow_ai_extra_options=False,
        priority="low",
    ),
    _spec(
        "Payment terms beyond policy",
        "When someone asks for payment terms longer than our maximum",
        keywords=["net 60", "net 90", "pay after 60 days", "pay net"],
        options=[
            ("Hold firm on terms", "Restate the configured maximum payment terms."),
            ("Offer a deposit structure", "Propose a deposit + balance schedule instead."),
        ],
        priority="high",
    ),
    _spec(
        "Exclusivity requested",
        "When a brand asks for category exclusivity",
        keywords=["exclusive", "exclusivity", "sole partner", "sole provider"],
        opportunity_types=["brand_deal"],
        options=[
            ("Decline exclusivity", "Pass on any exclusivity grant."),
            ("Offer paid, time-limited exclusivity", "Price a bounded exclusivity window."),
        ],
        priority="high",
    ),
    _spec(
        "Bulk book order",
        "When a school or org asks about ordering books in bulk",
        keywords=["book order", "bulk order", "buy copies", "order books"],
        opportunity_types=["book_order"],
        options=[("Send bulk pricing", "Share the bulk-tier pricing sheet.")],
    ),
    _spec(
        "Reschedule or cancellation request",
        "When someone wants to reschedule or cancel a confirmed booking",
        keywords=["reschedule", "need to cancel", "postpone", "push the date"],
        options=[
            (
                "Offer new dates within cancellation policy",
                "Propose alternatives per the configured policy.",
            ),
            ("Confirm cancellation terms", "State the cancellation policy plainly."),
        ],
    ),
    _spec(
        "Conference CFP",
        "When a conference sends a call for speakers",
        keywords=["call for speakers", "cfp", "submit a proposal", "speaker application"],
        opportunity_types=["speaking"],
        options=[
            ("Draft an application", "Put together a CFP submission in voice."),
            ("Pass on this one", "Skip if it's not a fit."),
        ],
    ),
    _spec(
        "Media kit request",
        "When someone asks for a media kit or one-sheet",
        keywords=["media kit", "press kit", "one sheet", "one-sheet"],
        options=[("Send media kit link", "Share the media kit URL directly.")],
        allow_ai_extra_options=False,
        priority="low",
    ),
    _spec(
        "Looks like spam or a bulk pitch",
        "When a message looks automated, mass-sent, or spammy",
        keywords=["unsubscribe", "this is an automated message", "act now", "limited time offer"],
        options=[("No action needed", "Leave it in the Spam & Risk lane.")],
        allow_ai_extra_options=False,
        priority="low",
    ),
]


async def install_default_playbooks(*, workspace_id: str, brand_id: str) -> list[ScenarioPlaybook]:
    """Idempotent by (brand_id, name) — safe to call more than once."""
    existing_names = {
        pb.name
        for pb in await ScenarioPlaybook.find(
            ScenarioPlaybook.workspace_id == workspace_id, ScenarioPlaybook.brand_id == brand_id
        ).to_list()
    }
    created: list[ScenarioPlaybook] = []
    for spec in DEFAULT_PLAYBOOK_SPECS:
        if spec["name"] in existing_names:
            continue
        playbook = ScenarioPlaybook(workspace_id=workspace_id, brand_id=brand_id, **spec)
        await playbook.insert()
        created.append(playbook)
    return created
