"""EmailProvider interface (Section 6, 8.1).

`StubEmailProvider` is free/offline and the default: it "sends" by just
returning a fake provider message id, so the whole triage → option-set →
approve → send pipeline is fully exercisable without a Gmail account.

`GmailEmailProvider` is a real adapter skeleton. It needs a Google Cloud
project + OAuth credentials to actually do anything (PLAN.md open
question 1) — until those exist, `get_email_provider()` keeps returning
the stub even if you start filling in Gmail-shaped config, so nothing
here can accidentally try to hit a real inbox.
"""

from __future__ import annotations

import uuid
from typing import Protocol


class SentEmail:
    def __init__(self, provider_message_id: str) -> None:
        self.provider_message_id = provider_message_id


class EmailProvider(Protocol):
    async def send(
        self, *, to: list[str], subject: str, body_text: str, in_reply_to: str = ""
    ) -> SentEmail: ...


class StubEmailProvider:
    """No network calls. Deterministic fake ids so tests can assert on them."""

    async def send(
        self, *, to: list[str], subject: str, body_text: str, in_reply_to: str = ""
    ) -> SentEmail:
        return SentEmail(provider_message_id=f"stub-email-{uuid.uuid4().hex[:12]}")


class GmailEmailProvider:
    """Real Gmail adapter — not wired to live traffic yet.

    Requires: a Google Cloud project, an Internal-app OAuth client
    (PLAN.md decision: Internal app avoids verification for customer-zero
    use), and per-user OAuth tokens stored encrypted at rest (Section
    14). None of that exists yet, so this class intentionally has no
    working implementation — filling it in is Phase 1 follow-up work
    once Gmail credentials are available.
    """

    async def send(
        self, *, to: list[str], subject: str, body_text: str, in_reply_to: str = ""
    ) -> SentEmail:
        raise NotImplementedError(
            "GmailEmailProvider requires OAuth credentials that aren't configured yet. "
            "See docs/SCOPES.md and PLAN.md open question 1."
        )


_provider: EmailProvider | None = None


def get_email_provider() -> EmailProvider:
    global _provider
    if _provider is not None:
        return _provider
    # Deliberately NOT gated on a "gmail configured" flag yet — Gmail
    # OAuth isn't implemented, so returning the stub is the only safe
    # default regardless of what's in .env.
    _provider = StubEmailProvider()
    return _provider
