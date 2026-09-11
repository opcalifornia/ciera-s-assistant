"""Append-only audit trail (Section 2 principle 7, Section 14).

Nothing updates or deletes an AuditLog entry. Policy decisions, auth
events, and every side-effecting action get written here.
"""

from typing import Any

from pydantic import Field
from pymongo import IndexModel

from app.models.base import WorkspaceScopedDocument


class AuditLog(WorkspaceScopedDocument):
    actor: str  # e.g. "user:<id>", "agent:triage", "system"
    action: str  # e.g. "policy.decision", "auth.login", "thread.send"
    target: str = ""  # e.g. "opportunity:<id>"
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Settings:
        name = "audit_log"
        indexes = [
            "workspace_id",
            IndexModel([("workspace_id", 1), ("created_at", -1)]),
        ]
