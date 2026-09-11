from typing import Any

from app.core.policy_engine import PolicyRequest, PolicyResult
from app.models.audit_log import AuditLog


async def log_event(
    *,
    workspace_id: str,
    actor: str,
    action: str,
    target: str = "",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str = "",
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        workspace_id=workspace_id,
        actor=actor,
        action=action,
        target=target,
        before=before,
        after=after,
        reason=reason,
        metadata=metadata or {},
    )
    await entry.insert()
    return entry


async def log_policy_decision(
    *, actor: str, request: PolicyRequest, result: PolicyResult
) -> AuditLog:
    return await log_event(
        workspace_id=str(request.workspace.id),
        actor=actor,
        action="policy.decision",
        target=request.action,
        after={
            "decision": result.decision.value,
            "permission_class": request.permission_class.value,
            "flags": sorted(request.flags),
        },
        reason=result.reason,
        metadata={"payload": request.payload},
    )
