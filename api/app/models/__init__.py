from app.models.audit_log import AuditLog
from app.models.brand import Brand
from app.models.user import User
from app.models.workspace import Workspace

DOCUMENT_MODELS = [Workspace, User, Brand, AuditLog]

__all__ = ["Workspace", "User", "Brand", "AuditLog", "DOCUMENT_MODELS"]
