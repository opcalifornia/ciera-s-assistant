"""Long-form Brand Brain documents (Section 4.1): book excerpts, past
talks, bios, and — most importantly for Phase 1 — real emails the talent
has written, used as retrieval examples for the voice-consistency check
(Section 4.1: "Drafts must pass a voice-consistency check").

`embedding` is populated at ingestion time via `EmbeddingProvider` (free
lexical stub by default, real Voyage embeddings once funded).
"""

from enum import StrEnum

from pydantic import Field
from pymongo import IndexModel

from app.models.base import WorkspaceScopedDocument


class BrandDocumentType(StrEnum):
    BOOK_EXCERPT = "book_excerpt"
    BIO = "bio"
    TALK_TRANSCRIPT = "talk_transcript"
    PAST_EMAIL = "past_email"
    FAQ = "faq"
    OTHER = "other"


class BrandDocument(WorkspaceScopedDocument):
    brand_id: str
    doc_type: BrandDocumentType
    title: str = ""
    text: str
    embedding: list[float] = Field(default_factory=list)

    class Settings:
        name = "brand_documents"
        indexes = ["workspace_id", IndexModel([("brand_id", 1)])]
