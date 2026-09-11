"""SMSProvider interface (PLAN.md Section 7 addendum).

Same shape as `EmailProvider`: a free `StubSMSProvider` is the default,
`TwilioSMSProvider` is a real adapter skeleton that needs a Twilio
account SID/auth token/number before it can do anything. Until those
are in `.env`, `get_sms_provider()` always returns the stub.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from app.core.config import get_settings


class SentSMS:
    def __init__(self, provider_message_id: str) -> None:
        self.provider_message_id = provider_message_id


class SMSProvider(Protocol):
    async def send(self, *, to: str, body_text: str) -> SentSMS: ...


class StubSMSProvider:
    """No network calls, no Twilio account required."""

    async def send(self, *, to: str, body_text: str) -> SentSMS:
        return SentSMS(provider_message_id=f"stub-sms-{uuid.uuid4().hex[:12]}")


class TwilioSMSProvider:
    """Real Twilio adapter — not wired to live traffic yet.

    Requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and a purchased
    TWILIO_SMS_NUMBER (a dedicated business number, never the talent's
    personal one). None of that is set up yet — see PLAN.md Section 7.
    """

    def __init__(self, account_sid: str, auth_token: str, from_number: str) -> None:
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._from_number = from_number

    async def send(self, *, to: str, body_text: str) -> SentSMS:
        raise NotImplementedError(
            "TwilioSMSProvider requires a Twilio account that isn't configured yet. "
            "See docs/SCOPES.md and PLAN.md Section 7."
        )


_provider: SMSProvider | None = None


def get_sms_provider() -> SMSProvider:
    global _provider
    if _provider is not None:
        return _provider
    settings = get_settings()
    if settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_sms_number:
        _provider = TwilioSMSProvider(
            settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_sms_number
        )
    else:
        _provider = StubSMSProvider()
    return _provider
