# OAuth & API Scopes

Documents every external scope GreenRoom requests, and why (Section 6
principle: "least-privilege API scopes; documented in docs/SCOPES.md").

No integration is wired up yet — this file is a placeholder populated as
each channel ships, starting with Gmail in Phase 1.

## Gmail (Phase 1)

**Not yet configured.** When implemented:

- App type: **Internal** (Google Workspace) for customer-zero use, per
  `PLAN.md` decision on Gmail scope strategy — avoids OAuth
  verification/CASA assessment until multi-tenant launch (Phase 6).
- Anticipated scopes (narrowest that work; finalize at implementation
  time):
  - `gmail.readonly` or `gmail.modify` — read inbox, needed for triage.
  - `gmail.send` — send approved replies.
  - `gmail.labels` — organize triaged threads.
- Tokens stored encrypted at rest; disconnect flow revokes and deletes
  stored tokens (Section 14).

## Google Calendar (Phase 3)

**Not yet configured.** Anticipated: `calendar.events` (read/write) for
holds, confirmations, and conflict detection.

## Instagram (Phase 3)

**Not yet configured.** Anticipated: Instagram API with Instagram Login,
`instagram_business_manage_messages` for DM webhooks.

## Twilio SMS (Phase 1, added post-Phase-0-plan)

**Not yet configured.** A dedicated business SMS/MMS number, not the
founder's personal number. No inbound-content scopes beyond what's needed
to receive/send on that one number.

## Stripe (Phase 2)

**Not yet configured.** Anticipated: restricted API key scoped to
invoices, payment links, and webhooks only — no account-level access.

## Google Sign-In (Phase 0, auth)

**Not yet configured** — Phase 0 ships email/password auth only. Google
Sign-In (`openid email profile`) is Section 6 scope, deferred until
there's a second real user to test RBAC against.
