"""Shared Beanie document mixins.

Every tenant-scoped collection embeds `WorkspaceScoped` so `workspace_id`
is never optional and every query helper can enforce isolation (Section
14: "workspace isolation tests").
"""

from datetime import UTC, datetime

from beanie import Document
from pydantic import Field


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampedDocument(Document):
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    class Settings:
        use_state_management = True


class WorkspaceScopedDocument(TimestampedDocument):
    workspace_id: str
