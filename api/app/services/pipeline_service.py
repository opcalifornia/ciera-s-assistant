"""The Agent Orchestrator (architecture diagram in PLAN.md): wires an
inbound message through Triage → Scenario Playbook matching → Brand
Voice → the Policy Engine, and persists the result.

This is the one place all four pieces meet, so it's also where "never
let the LLM set policy_status" (Section 4.3.1) is enforced structurally:
the agents return schema objects with `policy_status=None`, and only
this function calls `evaluate()` and fills it in.
"""

from __future__ import annotations

from app.agents.brand_voice import BrandVoiceAgent
from app.agents.schemas import OptionSetResult, TriageResult
from app.agents.triage import TriageAgent
from app.core.policy_engine import PolicyRequest, ToolPermissionClass, evaluate
from app.models.brand import Brand
from app.models.option_set import OptionSet, OptionSetStatus, PersistedOption, PersistedQuickReply
from app.models.playbook import ScenarioPlaybook
from app.models.thread import Channel, Message, MessageDirection, Thread, TriageSnapshot
from app.models.workspace import Workspace
from app.providers.llm import get_llm_provider
from app.services import playbook_service


async def _find_or_create_thread(
    *,
    workspace_id: str,
    brand_id: str,
    channel: Channel,
    participant: str,
    subject: str,
    provider_thread_id: str = "",
) -> Thread:
    query = [
        Thread.workspace_id == workspace_id,
        Thread.brand_id == brand_id,
        Thread.channel == channel,
    ]
    if provider_thread_id:
        query.append(Thread.provider_thread_id == provider_thread_id)
    else:
        query.append(Thread.participants == [participant])

    thread = await Thread.find_one(*query)
    if thread is not None:
        return thread

    thread = Thread(
        workspace_id=workspace_id,
        brand_id=brand_id,
        channel=channel,
        provider_thread_id=provider_thread_id,
        participants=[participant],
        subject=subject,
    )
    await thread.insert()
    return thread


def _policy_status_for(
    *, action: str, workspace: Workspace, opportunity_type: str | None, flags: set[str]
) -> tuple[str, str]:
    result = evaluate(
        PolicyRequest(
            action=action,
            permission_class=ToolPermissionClass.SIDE_EFFECT,
            workspace=workspace,
            opportunity_type=opportunity_type,
            flags=frozenset(flags),
        )
    )
    return result.decision.value, result.reason


def _persist_option_set(
    *,
    workspace_id: str,
    thread_id: str,
    message_id: str,
    option_result: OptionSetResult,
    workspace: Workspace,
    opportunity_type: str | None,
    flags: set[str],
) -> OptionSet:
    persisted_options = []
    for opt in option_result.options:
        status, reason = _policy_status_for(
            action=opt.action, workspace=workspace, opportunity_type=opportunity_type, flags=flags
        )
        persisted_options.append(
            PersistedOption(
                label=opt.label,
                strategy=opt.strategy,
                tradeoff=opt.tradeoff,
                likely_outcome=opt.likely_outcome,
                draft=opt.draft,
                numbers=opt.numbers,
                is_recommended=opt.is_recommended,
                recommendation_reason=opt.recommendation_reason,
                action=opt.action,
                policy_status=status,
                policy_reason=reason,
            )
        )

    persisted_quick_replies = []
    for qr in option_result.quick_replies:
        status, reason = _policy_status_for(
            action=qr.action, workspace=workspace, opportunity_type=opportunity_type, flags=flags
        )
        persisted_quick_replies.append(
            PersistedQuickReply(
                label=qr.label,
                draft=qr.draft,
                action=qr.action,
                policy_status=status,
                policy_reason=reason,
            )
        )

    return OptionSet(
        workspace_id=workspace_id,
        thread_id=thread_id,
        message_id=message_id,
        playbook_id=option_result.playbook_id,
        options=persisted_options,
        quick_replies=persisted_quick_replies,
        status=OptionSetStatus.PENDING,
    )


async def ingest_inbound_message(
    *,
    workspace_id: str,
    brand: Brand,
    channel: Channel,
    sender: str,
    subject: str,
    body: str,
    provider_thread_id: str = "",
) -> tuple[Thread, Message, OptionSet]:
    """The end-to-end pipeline for one inbound message. Free by default —
    every LLM call inside Triage/Brand Voice goes through `LLMProvider`,
    which is the offline stub unless a real key is configured."""
    workspace = await Workspace.get(workspace_id)
    if workspace is None:
        raise ValueError(f"Workspace {workspace_id} not found")

    thread = await _find_or_create_thread(
        workspace_id=workspace_id,
        brand_id=str(brand.id),
        channel=channel,
        participant=sender,
        subject=subject,
        provider_thread_id=provider_thread_id,
    )

    message = Message(
        workspace_id=workspace_id,
        thread_id=str(thread.id),
        direction=MessageDirection.INBOUND,
        channel=channel,
        sender=sender,
        recipients=[],
        subject=subject,
        body_text=body,
    )
    await message.insert()

    llm = get_llm_provider()
    triage_result: TriageResult = await TriageAgent(llm).run(
        brand=brand, sender=sender, subject=subject, body=body, workspace_id=workspace_id
    )
    message.injection_flag = "suspicious_injection" in triage_result.flags
    await message.save()

    thread.last_message_at = message.sent_or_received_at
    thread.subject = thread.subject or subject
    thread.triage = TriageSnapshot(
        classification=triage_result.classification.value,
        opportunity_type=triage_result.opportunity_type,
        summary=triage_result.summary,
        urgency=triage_result.urgency.value,
        estimated_deal_value=triage_result.estimated_deal_value,
        flags=sorted(triage_result.flags),
        missing_fields=triage_result.missing_fields,
        recommended_next_action=triage_result.recommended_next_action,
        confidence=triage_result.confidence,
    )
    thread.needs_a_look = triage_result.needs_a_look
    await thread.save()

    playbook: ScenarioPlaybook | None = await playbook_service.find_matching_playbook(
        workspace_id=workspace_id,
        brand_id=str(brand.id),
        sender=sender,
        subject=subject,
        body=body,
        triage=triage_result,
    )

    option_result: OptionSetResult = await BrandVoiceAgent(llm).run(
        brand=brand,
        triage=triage_result,
        sender=sender,
        subject=subject,
        body=body,
        workspace_id=workspace_id,
        playbook=playbook,
    )

    option_set = _persist_option_set(
        workspace_id=workspace_id,
        thread_id=str(thread.id),
        message_id=str(message.id),
        option_result=option_result,
        workspace=workspace,
        opportunity_type=triage_result.opportunity_type,
        flags=triage_result.flags,
    )
    await option_set.insert()

    return thread, message, option_set
