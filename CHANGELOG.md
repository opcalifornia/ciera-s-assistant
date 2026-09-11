# Changelog

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
