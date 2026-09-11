# GreenRoom

> Working codename only — run a trademark search before public launch.

AI front office for multi-hyphenate talent: one unified inbox across
email and text, strategic reply options in the talent's voice, and a
policy engine that keeps every send, quote, and commitment inside the
talent's rules — nothing goes out without approval unless explicitly
allowed to.

See `PLAN.md` for architecture, decisions, and the phased roadmap. See
`CHANGELOG.md` for what's shipped so far and `DEMO.md` for a walkthrough
of the current state.

## Quickstart

Everything below runs for free — no API keys required. Paid providers
(Anthropic, Voyage, Twilio, etc.) are wired behind interfaces but stay on
their free/offline stub implementations until you add real keys to
`.env`.

```bash
cp .env.example .env

make dev     # starts mongo, redis, api, worker, web via docker compose
make seed    # (in another terminal) seeds a demo workspace + login
make test    # backend test suite, runs against an in-memory Mongo
make eval    # validates the eval fixture set (Section 13)
```

Once `make dev` is running:
- API: http://localhost:8000 (docs at `/docs`)
- Web: http://localhost:5173
- Log in with the credentials `make seed` prints, or register a new
  workspace from the login screen.

## Repo layout

```
api/      FastAPI backend (agents, models, providers, routers, evals)
web/      React + Vite + TypeScript frontend (PWA)
seed/     Local demo data + voice sample intake
docs/     SCOPES.md, LEGAL_REVIEW.md
```

## Status

Phase 0 (foundation) is in progress — see `PLAN.md` Section 15 for the
full phased roadmap and acceptance criteria.
