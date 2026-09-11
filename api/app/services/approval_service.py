"""The approval flow (Section 4.3.3): Send / Adjust / Write my own.

The human picking an option and hitting Send *is* the approval for a
REQUIRE_APPROVAL decision — this module re-evaluates the Policy Engine
at send time (autonomy or the kill switch may have changed since the
option set was generated) and only a DENY blocks it. `Blend` (Section
4.3.3) is out of scope for Phase 1 — noted as a follow-up, not silently
dropped.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings
from app.core.models_config import ModelTier
from app.core.policy_engine import PolicyDecision, PolicyRequest, ToolPermissionClass, evaluate
from app.models.option_set import OptionChoice, OptionSet, OptionSetStatus
from app.models.thread import Channel, Message, MessageDirection, Thread
from app.models.workspace import Workspace
from app.providers.email import get_email_provider
from app.providers.llm import get_llm_provider
from app.providers.sms import get_sms_provider
from app.services import audit_service


class ApprovalError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class ChoiceInput:
    kind: str  # "option" | "quick_reply" | "custom"
    index: int | None = None
    custom_text: str | None = None
    adjusted_text: str | None = None  # text after Adjust/Edit, if different from the original draft


def _resolve_draft(option_set: OptionSet, choice: ChoiceInput) -> tuple[str, str, str, str]:
    """Returns (label, draft_text, action, original_draft_for_diffing)."""
    if choice.kind == "option":
        if choice.index is None or not (0 <= choice.index < len(option_set.options)):
            raise ApprovalError("Invalid option index")
        opt = option_set.options[choice.index]
        return opt.label, (choice.adjusted_text or opt.draft), opt.action, opt.draft
    if choice.kind == "quick_reply":
        if choice.index is None or not (0 <= choice.index < len(option_set.quick_replies)):
            raise ApprovalError("Invalid quick reply index")
        qr = option_set.quick_replies[choice.index]
        return qr.label, (choice.adjusted_text or qr.draft), qr.action, qr.draft
    if choice.kind == "custom":
        if not choice.custom_text:
            raise ApprovalError("custom_text is required for a custom reply")
        return "Write my own", choice.custom_text, "message.send_reply", ""
    raise ApprovalError(f"Unknown choice kind: {choice.kind}")


async def _send_via_channel(*, channel: Channel, to: str, subject: str, body_text: str) -> str:
    if channel == Channel.EMAIL:
        sent_email = await get_email_provider().send(to=[to], subject=subject, body_text=body_text)
        return sent_email.provider_message_id
    if channel == Channel.SMS:
        sent_sms = await get_sms_provider().send(to=to, body_text=body_text)
        return sent_sms.provider_message_id
    raise ApprovalError(f"Sending on channel '{channel.value}' isn't implemented yet.")


async def choose_and_send(
    *, option_set_id: str, user_id: str, workspace_id: str, choice: ChoiceInput, send: bool
) -> tuple[OptionSet, Message | None]:
    option_set = await OptionSet.get(option_set_id)
    if option_set is None or option_set.workspace_id != workspace_id:
        raise ApprovalError("Option set not found", status_code=404)
    if option_set.status != OptionSetStatus.PENDING:
        raise ApprovalError(f"Option set is already '{option_set.status.value}'")

    thread = await Thread.get(option_set.thread_id)
    if thread is None:
        raise ApprovalError("Thread not found", status_code=404)

    workspace = await Workspace.get(workspace_id)
    if workspace is None:
        raise ApprovalError("Workspace not found", status_code=404)

    label, draft_text, action, original_draft = _resolve_draft(option_set, choice)
    if send and not draft_text.strip():
        raise ApprovalError(
            "This option has no draft text yet (e.g. 'Needs your call' / 'Review manually') — "
            "write your own reply before sending."
        )

    opportunity_type = thread.triage.opportunity_type if thread.triage else None
    flags = set(thread.triage.flags) if thread.triage else set()

    policy_result = evaluate(
        PolicyRequest(
            action=action,
            permission_class=ToolPermissionClass.SIDE_EFFECT,
            workspace=workspace,
            opportunity_type=opportunity_type,
            flags=frozenset(flags),
        )
    )
    await audit_service.log_policy_decision(
        actor=f"user:{user_id}",
        request=PolicyRequest(
            action=action,
            permission_class=ToolPermissionClass.SIDE_EFFECT,
            workspace=workspace,
            opportunity_type=opportunity_type,
            flags=frozenset(flags),
        ),
        result=policy_result,
    )

    if policy_result.decision == PolicyDecision.DENY:
        raise ApprovalError(f"Blocked by policy: {policy_result.reason}", status_code=403)

    outbound_message: Message | None = None
    if send:
        recipient = thread.participants[0] if thread.participants else ""
        provider_message_id = await _send_via_channel(
            channel=thread.channel, to=recipient, subject=thread.subject, body_text=draft_text
        )
        outbound_message = Message(
            workspace_id=workspace_id,
            thread_id=str(thread.id),
            direction=MessageDirection.OUTBOUND,
            channel=thread.channel,
            sender=f"assistant:{workspace_id}",
            recipients=[recipient],
            subject=thread.subject,
            body_text=draft_text,
            metadata={"provider_message_id": provider_message_id, "approved_by": user_id},
        )
        await outbound_message.insert()
        thread.last_message_at = outbound_message.sent_or_received_at
        await thread.save()

        await audit_service.log_event(
            workspace_id=workspace_id,
            actor=f"user:{user_id}",
            action="thread.send",
            target=f"thread:{thread.id}",
            after={"channel": thread.channel.value, "label": label},
        )

    option_set.status = OptionSetStatus.CHOSEN
    option_set.chosen_option_index = choice.index if choice.kind == "option" else -1
    await option_set.save()

    was_edited = bool(choice.adjusted_text) and choice.adjusted_text != original_draft
    await OptionChoice(
        workspace_id=workspace_id,
        option_set_id=str(option_set.id),
        playbook_id=option_set.playbook_id,
        chosen_label=label,
        was_edited=was_edited,
        was_custom=choice.kind == "custom",
        edit_distance=abs(len(draft_text) - len(original_draft)) if was_edited else 0,
        chosen_by=user_id,
    ).insert()

    return option_set, outbound_message


async def adjust_draft(*, original_draft: str, instruction: str, workspace_id: str) -> str:
    """Section 4.3.3 'Adjust': regenerate one option's draft with a free-
    text instruction ("warmer", "shorter", "mention the book"). Returns
    the original draft unchanged (never garbled stub text) when no real
    LLM is configured — honest degradation rather than fake output."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        return original_draft

    llm = get_llm_provider()
    response = await llm.complete(
        system=(
            "Rewrite the following draft reply per the instruction. Preserve its strategic "
            "intent and any commitments (numbers, terms) unless the instruction says otherwise. "
            "Respond with ONLY the rewritten draft text, no preamble."
        ),
        messages=[
            {"role": "user", "content": f"Draft:\n{original_draft}\n\nInstruction: {instruction}"}
        ],
        tier=ModelTier.BALANCED,
        workspace_id=workspace_id,
    )
    return response.text.strip() or original_draft
