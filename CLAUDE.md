# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

PropTalk US — an AI voice agent (Retell) that answers leasing calls for small US property managers: answers listing questions from the client's real data, books tours, triages maintenance, takes messages, and emails a post-call summary. A FastAPI backend exposes the tools the Retell agent calls over HTTPS.

The project is built in numbered phases on a **$0-until-outreach** budget. The canonical planning docs in `docs/` are the source of truth — read them before non-trivial work:
- `docs/prd.md` — requirements, ICP, success gates, compliance.
- `docs/architecture.md` — tech stack, data model, API surface, request flows, target folder tree.
- `docs/rules.md` — engineering rules, error handling, security, compliance-in-code (**read before writing backend code**).
- `docs/phases.md` — build order + live progress tracker (check the boxes to see what's done / next).
- `docs/RETELL_AGENT_CONFIG.md` — agent system prompt + the 6 tool JSON schemas (the contract the backend must satisfy).
- `docs/PROPTALK_US_BUILD_PLAYBOOK.md` — the full business+build playbook (schema, seed spec, GTM).

**Current state:** Phase 3 complete — the Retell agent (gpt-4.1, 6 tools, webhook) is provisioned from code (`backend/scripts/retell_provision.py`) behind a `cloudflared` tunnel, and a full web call qualified a renter and booked a tour. Phase 4 (real Cal.com slots/booking + Resend summary email) is next. Keep `docs/phases.md` updated as phases complete.

## Environment

Windows + PowerShell. Python 3.14 in a venv at `backend/.venv`. Secrets live in a gitignored `.env` at the **repo root** (`app/db.py` loads it via `parents[2]`); `.env.example` documents the keys. `secrets/` is gitignored and holds a real credential — never track it.

## Commands

Run from `D:\US\backend` with the venv active (`.\.venv\Scripts\Activate.ps1`), or call `.\.venv\Scripts\python.exe` directly.

```powershell
# install deps
pip install -r requirements.txt

# run the API (dev)
uvicorn app.main:app --reload --port 8000        # http://127.0.0.1:8000/health , /docs

# database (needs DATABASE_URL in root .env — Supabase Session pooler URI)
python scripts\apply_sql.py                        # apply schema.sql + seed (idempotent)
python scripts\test_search.py                      # Phase 1 verification: 5 search scenarios

# expose backend to Retell (Phase 3; no tunnel tool installed yet)
cloudflared tunnel --url http://localhost:8000     # then update Retell function URLs
```

There is no test framework yet. Verification is script-based (`scripts/test_search.py`) and, from Phase 2, curl-first: every endpoint is proven with `curl` before it's attached to Retell. Add per-endpoint curl scripts under `backend/tests/curl/`.

## Architecture that isn't obvious from a single file

- **Multi-tenant by `client_id`, always.** Every table carries `client_id`; every query filters by it. Per-client agent differences (company name, agent name, office hours) ride on Retell **dynamic variables**, not duplicated agents. The demo tenant is Willowbrook, fixed UUID `11111111-1111-1111-1111-111111111111`.
- **The agent is stateless about facts — the backend is the source of truth.** The agent may only state facts returned by a tool *in that call*. Correspondingly the backend must never fabricate a listing/slot; if nothing matches, return a small `{"ok": false, ...}` the agent can speak around. The seed includes a `leased` unit specifically to prove search excludes unavailable inventory.
- **Latency is a hard product constraint.** Tools must return **< 1KB JSON in < 800ms p95**. `get_available_listings` returns ≤ 3 rows, whitelisted fields only. No blocking I/O in handlers; use `httpx` with explicit timeouts for Cal.com/Twilio/Resend.
- **`book_tour` must be idempotent** (guard on `retell_call_id` + slot) and never overwrite an existing booking — on conflict, offer the next slot. `/webhooks/retell` must return 2xx fast, verify the Retell signature, tolerate duplicate deliveries (upsert on `retell_call_id`), and enforce the pilot `minutes_cap` there.
- **Compliance is code, not just prompt.** SMS is gated on `sms_consent` (TCPA) and feature-flagged off (`FEATURE_SMS_ENABLED=false`) until Twilio is funded. Fair-housing deflection lives in the agent prompt; the backend must never store/return neighborhood or demographic judgments. Store timestamps in **UTC**, speak **client-local** time (`clients.timezone`).
- **Config discipline:** tunables (greeting, emergency definitions, caps, flags) belong in `app/config.py` + `clients` rows, never hardcoded in handlers.

The six tools the backend must implement (schemas in `docs/RETELL_AGENT_CONFIG.md`): `get_available_listings`, `check_tour_slots`, `book_tour`, `create_maintenance_ticket`, `escalate_emergency`, `take_message`, plus `POST /webhooks/retell`.

## Data-access pattern

Direct Postgres via `psycopg` v3 (not the Supabase REST API — the "auto-expose tables" option is intentionally off). `app/db.py` `get_connection()` reads `DATABASE_URL`. Queries use named params with explicit casts (e.g. `%(beds)s::int`) so NULL filters type-check; see `app/services/listings.py` as the reference pattern. SQL files under `backend/sql/` are the canonical schema/seed and are also paste-ready for the Supabase SQL editor.

## Conventions

- Python 3.11+ style, full type hints, thin routes calling one service module per domain, pydantic models for tool request/response shapes.
- Git commits end with the trailer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Before committing, confirm `.env`, `secrets/`, and `.venv/` are not staged. Commit per completed phase and check the box in `docs/phases.md`.
