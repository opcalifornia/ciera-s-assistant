"""Scenario Playbook matching (Section 4.3.2): "Triage checks every
message against active playbooks."

Deterministic keyword/domain/opportunity-type matching — free, and
matches before an LLM is ever called, so playbook-driven scenarios work
identically regardless of whether a real LLM key is configured.
"""

from app.agents.schemas import TriageResult
from app.models.playbook import ScenarioPlaybook


def _sender_domain(sender: str) -> str:
    return sender.rsplit("@", 1)[-1].strip().lower() if "@" in sender else ""


def matches(
    playbook: ScenarioPlaybook, *, sender: str, subject: str, body: str, triage: TriageResult
) -> bool:
    if not playbook.enabled:
        return False

    criteria = playbook.compiled_criteria
    text = f"{subject}\n{body}".lower()

    if criteria.keywords and not any(kw.lower() in text for kw in criteria.keywords):
        return False

    if criteria.sender_domains:
        domain = _sender_domain(sender)
        if not any(
            domain == d.lower() or domain.endswith(f".{d.lower()}") for d in criteria.sender_domains
        ):
            return False

    if criteria.opportunity_types and triage.opportunity_type not in criteria.opportunity_types:
        return False

    if criteria.min_value is not None:
        if triage.estimated_deal_value is None or triage.estimated_deal_value < criteria.min_value:
            return False

    if criteria.max_value is not None:
        if triage.estimated_deal_value is None or triage.estimated_deal_value > criteria.max_value:
            return False

    # A playbook with no criteria at all matches nothing — an empty
    # criteria set is a misconfiguration, not a universal match.
    has_any_criterion = bool(
        criteria.keywords or criteria.sender_domains or criteria.opportunity_types
    )
    return has_any_criterion


async def find_matching_playbook(
    *, workspace_id: str, brand_id: str, sender: str, subject: str, body: str, triage: TriageResult
) -> ScenarioPlaybook | None:
    playbooks = await ScenarioPlaybook.find(
        ScenarioPlaybook.workspace_id == workspace_id,
        ScenarioPlaybook.brand_id == brand_id,
        ScenarioPlaybook.enabled == True,  # noqa: E712 (Beanie query operator, not a bool comparison)
    ).to_list()
    for playbook in playbooks:
        if matches(playbook, sender=sender, subject=subject, body=body, triage=triage):
            return playbook
    return None
