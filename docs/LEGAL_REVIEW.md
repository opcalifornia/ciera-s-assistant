# Legal Review Checklist

Items for an attorney before multi-tenant launch (Section 8.6). Nothing
here has been reviewed by counsel yet — this is a checklist, not advice,
and none of it should be read as a legal conclusion.

- [ ] **California Talent Agencies Act exposure** — if GreenRoom ever
      procures engagements for other artists (not just the founder),
      especially under any commission-based model, this needs review
      before that model ships.
- [ ] **Bot disclosure laws** — the AI assistant's disclosure language
      (Section 2 principle 4, Section 8.4) needs to satisfy applicable
      state bot-disclosure statutes, not just be "honest if asked."
- [ ] **CAN-SPAM and state email laws** — outreach sequences (Section
      8.3) implement the mechanical requirements (unsubscribe headers,
      physical address); counsel should confirm state-law add-ons before
      Phase 4 ships.
- [ ] **FTC endorsement disclosure obligations** — brand deal contracts
      (Section 4.8) should be checked against current FTC guidance on
      influencer disclosure before the Contracts agent's red/yellow/green
      flags are treated as authoritative.
- [ ] **Privacy policy, Terms of Service, data retention policy** — none
      exist yet; required before any non-founder workspace signs up
      (Phase 6).
- [ ] **Google API Services User Data Policy** — Gmail integration
      (Phase 1) must comply, and multi-tenant Gmail access requires the
      CASA security assessment referenced in Section 8.1.
- [ ] **Meta Platform Terms** — Instagram DM integration (Phase 3) must
      comply with Meta's platform policy, including the 24-hour messaging
      window and rate limits.
- [ ] **Minors / school outreach** — confirm the "adult staff only, never
      collect student data" policy (Section 2 principle 8) satisfies
      COPPA and FERPA-adjacent concerns before Prospector's school
      outreach (Phase 4) goes live.

This file grows as each phase ships a feature that touches one of these
areas — it is not meant to be resolved all at once.
