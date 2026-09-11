# Phase 0 Demo

Everything below runs for free — no API keys, no paid services. Validated
in this environment: `pytest` (17/17 passing), `ruff check` (clean),
`mypy` (clean), `python -m evals.runner` (10/10 fixtures valid), and the
web app (`npm run lint` / `typecheck` / `build`, all clean). Actually
running `docker compose up` requires a Docker daemon, which this sandbox
doesn't have — do that step locally to see it end-to-end in a browser.

## 1. Start everything

```bash
cp .env.example .env
make dev
```

This builds and starts `mongo`, `redis`, `api` (FastAPI on :8000), `worker`
(ARQ), and `web` (Vite on :5173).

## 2. Seed a demo workspace

In another terminal:

```bash
make seed
```

Prints a login email/password for a demo workspace ("Demo Talent Co.")
with a demo brand ("Jordan Rivers" / assistant "Nova") already configured
with values, no-go categories, availability, and business terms.

## 3. Walk through the app

- Open http://localhost:5173 → you land on the login screen (ChatGPT-style
  minimal design: Inter font, near-monochrome, single accent color, dark
  mode follows system preference).
- Log in with the seeded credentials, or click "New here? Create a
  workspace" to register your own from scratch — this exercises
  `POST /auth/register`, which creates a `Workspace` + owner `User` in one
  step (Section 1: the founder is always the first owner).
- You land on **Today**, showing who you're signed in as, your role, and
  your workspace name.
- Click **Engage kill switch** — this calls `POST /workspaces/me/kill-switch`.
  Toggling it flips `Workspace.kill_switch`, which the Policy Engine reads
  on every `SIDE_EFFECT` evaluation: with it engaged, `evaluate()` returns
  `DENY` for every side-effecting action regardless of autonomy level
  (Section 11: "one tap in the app stops all automated sending
  instantly"). There's nothing to auto-send yet in Phase 0, but the gate
  itself is live and tested (`tests/test_policy_engine.py`).

## 4. What's provable without the browser

```bash
cd api
make test    # 17 tests: full register/login/me/refresh flow against an
             # in-memory Mongo, plus 12 Policy Engine unit tests covering
             # every autonomy level, the kill switch, hard-deny actions,
             # and always-escalate flags (scam/injection/low-confidence).
make eval    # validates all 10 Section 13 fixtures against the schema
             # and required-coverage checks (brand deal + safety
             # categories represented, no duplicate ids).
```

## 5. What's explicitly NOT here yet

No agents, no Gmail/SMS/Instagram ingestion, no triage, no reply options,
no negotiation. Phase 0 is the foundation those land on: auth, the
workspace/brand data model, the policy engine (the thing every future
agent's output has to pass through), the audit log, and an `LLMProvider`
interface that costs nothing until a real Anthropic key is added to
`.env`. See `PLAN.md` Section 15 for what Phase 1 adds.
