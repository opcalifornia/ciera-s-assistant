"""User accounts with workspace-scoped RBAC roles (Section 6, 14)."""

from enum import StrEnum

from pydantic import BaseModel, EmailStr, Field
from pymongo import IndexModel

from app.models.base import WorkspaceScopedDocument


class Role(StrEnum):
    OWNER = "owner"
    MANAGER = "manager"
    ASSISTANT = "assistant"
    VIEWER = "viewer"


class NotificationPrefs(BaseModel):
    push_enabled: bool = True
    email_digest: bool = True


class User(WorkspaceScopedDocument):
    email: EmailStr
    hashed_password: str
    full_name: str = ""
    role: Role = Role.OWNER
    notification_prefs: NotificationPrefs = Field(default_factory=NotificationPrefs)
    is_active: bool = True

    class Settings:
        name = "users"
        indexes = [
            IndexModel("email", unique=True),
            "workspace_id",
        ]
