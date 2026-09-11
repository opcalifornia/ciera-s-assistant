from app.models.audit_log import AuditLog
from app.models.brand import Brand
from app.models.brand_document import BrandDocument
from app.models.offering import Offering
from app.models.opportunity import Opportunity
from app.models.option_set import OptionChoice, OptionSet
from app.models.playbook import ScenarioPlaybook
from app.models.thread import Message, Thread
from app.models.user import User
from app.models.workspace import Workspace

DOCUMENT_MODELS = [
    Workspace,
    User,
    Brand,
    AuditLog,
    Thread,
    Message,
    BrandDocument,
    Offering,
    Opportunity,
    ScenarioPlaybook,
    OptionSet,
    OptionChoice,
]

__all__ = [
    "Workspace",
    "User",
    "Brand",
    "AuditLog",
    "Thread",
    "Message",
    "BrandDocument",
    "Offering",
    "Opportunity",
    "ScenarioPlaybook",
    "OptionSet",
    "OptionChoice",
    "DOCUMENT_MODELS",
]
