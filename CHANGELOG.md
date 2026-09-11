# Changelog

## Phase 2 (partial) — Deal Desk

- `Opportunity` model + pipeline stage machine (Section 9.3): the full
  `new → ... → closed_won` happy path plus `closed_lost`/`declined_by_talent`/
  `ghosted`/`on_hold`, with `can_transition()` enforcing legal moves and
  `APPROVAL_GATED_STAGES` marking `verbal_yes` and beyond. Every
  opportunity-typed thread now gets an `Opportunity` record, merging in
  newly extracted fields as follow-up messages arrive.
- Rate cards graduated (Section 9.1/9.2): `Offering` gained `modifiers`
  (generic additive/multiplicative rate adjustments) and a
  `concession_ladder` (every discount paired with a required trade).
  `app/services/pricing_service.py` is the deterministic math — floor/
  target comparisons, modifier application, and picking the smallest
  sufficient concession for a given budget.
- Deal Desk negotiation agent (`app/agents/deal_desk.py`) — deliberately
  plain, deterministic code implementing Section 9.4's turn algorithm:
  request missing info, confirm scope at budget, counter within the
  concession ladder, quote at anchor, or decline below floor. A final
  guard re-checks every quoted amount against the floor before
  returning. The floor number itself never appears in any output.
- This is the first agent that can produce a **real, correct, zero-cost
  reply** without any LLM key — `draft_reply_option()` templates a
  correct quote/counter/decline straight from the deterministic
  decision. Brand Voice uses it to anchor the option set (always
  recommended, numbers grounded) and, when a real LLM key exists, adds
  additional strategically distinct options on top of the same figures.
- New Policy Engine action ids wired to the L2 allow-list
  (`message.request_missing_info`, `message.send_standard_quote_at_or_above_target`,
  `message.send_counter_within_concession_ladder_above_target`) plus a
  new `message.send_decline_below_floor` action that always requires
  approval.
- Frontend: a **Brand Brain** page to configure offerings (anchor/
  target/floor + one concession rung) from the browser — no curl
  required to try Deal Desk.
- Guardrail tests (Section 9.5): never quotes below floor even under a
  misconfigured rate card, never reveals the floor number, concession
  trades always paired with a "requires", smallest-sufficient-concession
  selection verified against multiple budget levels.

## Phase 0 — Foundation

- Repo scaffolding: FastAPI backend (`api/`), React/Vite/TS frontend
  (`web/`), Docker Compose (mongo, redis, api, worker, web).
- GitHub Actions CI: ruff, mypy, pytest, eval-fixture validation for the
  API; eslint, tsc, build for the web app.
- Config system: single `app/core/config.py` (env vars) and
  `app/core/models_config.py` (LLM tier → model ID mapping).
- Auth + RBAC: JWT access/refresh tokens, bcrypt password hashing,
  `owner/manager/assistant/viewer` roles, workspace-scoped `/auth/*`
  endpoints.
- Core data models (Beanie/MongoDB): `Workspace` (autonomy config, kill
  switch), `User`, `Brand` (Brand Brain skeleton), `AuditLog`
  (append-only).
- `LLMProvider` interface with a free `StubLLMProvider` default and a
  swappable `AnthropicLLMProvider`; Langfuse tracing hook that no-ops
  until explicitly enabled.
- Policy Engine (`app/core/policy_engine.py`): deterministic
  ALLOW/REQUIRE_APPROVAL/DENY evaluation over tool permission classes,
  the autonomy ladder (L0/L1/L2), hard-deny actions, the kill switch, and
  always-escalate flags (`scam_suspected`, `suspicious_injection`,
  `low_confidence`) — every decision loggable to the audit trail.
- Eval harness skeleton (`api/evals/`): schema-validated fixture format
  plus 10 starter fixtures spanning brand deals, speaking, schools, and
  safety/injection/scam cases (Section 13).
- Seed script (`seed/demo_workspace.py`): idempotent demo workspace,
  founder user, and brand.
- Frontend: minimal login/register + a "Today" page (workspace info, kill
  switch toggle) in a ChatGPT-style minimal design (Inter font,
  near-monochrome palette, single accent color, light/dark).
- Docs: `docs/SCOPES.md` and `docs/LEGAL_REVIEW.md` stubs, updated
  `README.md`.
- Product addendum: SMS added as a first-class channel (via Twilio)
  alongside Gmail, promoted from unplanned to Phase 1 — see `PLAN.md`
  Section 7.
- Product rename: **Ciera's Assistant** (GreenRoom was the working
  codename during planning).

## Phase 1 — Brand Brain + Inbox + Drafts + Approvals

- Deterministic safety pre-screen (`app/core/safety_screen.py`): free,
  LLM-independent regex/keyword detection for prompt injection (Section
  2 principle 3) and scam patterns (Section 4.4.6), runs on every
  inbound message before any LLM call.
- Unified inbox data model: `Thread` + `Message`, channel-agnostic
  (`email | sms | dm | intake`), with a denormalized triage snapshot and
  a "needs a look" lane for low-confidence classifications.
- `EmailProvider` / `SMSProvider` interfaces: free `Stub` implementations
  by default; `GmailEmailProvider` / `TwilioSMSProvider` adapter
  skeletons that activate once real credentials are configured (neither
  is live yet — both need accounts/OAuth this workspace doesn't have).
- Triage agent (`app/agents/triage.py`): classifies every inbound
  message, extracts fields, and — critically — the deterministic safety
  flags always override whatever the LLM concluded, verified by eval.
- Brand Brain expansion: `Offering` (opportunity type, anchor/target/floor
  numbers) and `BrandDocument` (bios, past emails, book excerpts) models;
  a free lexical-similarity `EmbeddingProvider` stub for retrieval, with
  a real Voyage AI adapter that activates once funded.
- Scenario Playbooks: deterministic keyword/domain/opportunity-type
  matcher plus 15 default playbooks (rate asks, unpaid podcast invites,
  school budget constraints, usage-rights/exclusivity flags, and more)
  installable per brand.
- Brand Voice agent (`app/agents/brand_voice.py`) — the signature
  feature: generates 2-4 strategically distinct reply options or
  quick-reply chips for simple messages; scam/injection-flagged threads
  always get a "Needs your call" card instead of an AI-authored draft.
  `policy_status` is computed by the Policy Engine, never by the agent.
- Agent Orchestrator (`app/services/pipeline_service.py`): wires Triage →
  Scenario Playbook matching → Brand Voice → Policy Engine for every
  inbound message, end to end.
- Approval flow (`app/services/approval_service.py`): Send / Edit /
  Adjust / Write my own. Re-evaluates the Policy Engine at send time —
  only a DENY (kill switch, hard-deny action) blocks a human-approved
  send; option-choice logging for the future learning loop. `Blend` is
  explicitly deferred, not silently dropped.
- Eval harness now runs for real (`api/evals/scoring.py`): scores the
  deterministic safety screen for false positives/negatives, verifies
  the "safety flags always override the classifier" guarantee via the
  full Triage agent, and — only when `ANTHROPIC_API_KEY` is set — scores
  real classification accuracy. Zero-cost by default.
- Frontend: Inbox (thread list + a "simulate an inbound message" tool
  standing in for the not-yet-connected Gmail/SMS webhooks) and a
  per-thread Approvals view (message transcript, option cards with
  policy-status badges, Send/Adjust/Write-my-own).
- Everything above runs against the free stub providers by default —
  validated end-to-end in a real browser (register → create brand →
  simulate an inbound message → triage → approve → send) as well as via
  33 backend tests.
