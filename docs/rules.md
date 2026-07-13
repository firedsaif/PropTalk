# PropTalk US — Engineering & Operating Rules

**Last updated:** 2026-07-13 · The "what to use / avoid / never break." Companion to [architecture.md](architecture.md).

---

## 1. Non-negotiable principles

1. **Multi-tenant from Day 1.** Every table carries `client_id`; every query filters by it. No global reads.
2. **Latency is the product.** Tool responses < 800ms p95; agent speaks < 1.2s after the caller stops. Kill any tool over 800ms.
3. **Facts come only from tools.** The agent never invents property data — and the backend never returns a fact it can't back with a row. If it isn't in the DB, it doesn't exist.
4. **Compact payloads.** Every tool returns < 1KB JSON. `get_available_listings` returns ≤ 3 listings, whitelisted fields only. Tokens are latency.
5. **One config source.** Greetings, emergency definitions, caps, feature flags live in `app/config.py` + `clients` rows. Never hardcode tunables in handlers.
6. **Log every tool call** with latency + payload (redact PII in logs — see §6). The gauntlet and the Monday report both read these logs.

## 2. Tech to use / avoid

**Use**
- FastAPI (async), pydantic v2 for every request/response model, `pydantic-settings` for env.
- `httpx` (async) for outbound calls (Cal.com, Twilio, Resend) with explicit timeouts.
- Parameterized SQL / the Supabase client — never string-built SQL.
- `python-dotenv` locally; Railway env vars in prod.
- Retell **dynamic variables** for per-client differences; Retell **web calls** for early testing.

**Avoid**
- No ORM heaviness early (SQLAlchemy models optional) — raw parameterized queries are fine and faster to reason about.
- No synchronous blocking I/O inside request handlers.
- No second LLM bill until needed — use Retell `call_analyzed` for summaries first.
- No new external service that isn't in [architecture.md](architecture.md) §2 without updating it first.
- No unbounded queries, no `SELECT *` across tenants, no returning full rows to the agent.

## 3. Error handling

- **Every outbound call has a timeout** (Cal.com/Twilio/Resend via `httpx`, default 5s hard, but the tool path itself must stay < 800ms — fail fast, don't hang the caller).
- **Tools degrade gracefully.** On failure return a clean, small JSON the agent can speak around, e.g. `{"ok": false, "reason": "no_slots"}` → agent offers to take a message. Never surface stack traces or 500s to Retell; catch and shape the response.
- **`book_tour` is the danger zone.** Make it **idempotent** (guard on `retell_call_id` + slot) so a retry never double-books. On a real conflict, return the next slot — **never overwrite** an existing booking.
- **Webhook is resilient.** `/webhooks/retell` must return 2xx fast and do heavy work (summary, email) without failing the request; verify the Retell signature; tolerate duplicate deliveries (upsert on `retell_call_id`).
- **Escalation is fire-and-return.** Alert the on-call human without blocking the agent's spoken confirmation; if SMS fails, fall back to a call, and log loudly.
- **Never invent on the backend either.** If a listing/slot isn't found, say so in the payload; don't fabricate a placeholder.

## 4. Coding conventions

- Python 3.11+, type hints everywhere, `ruff` + `black` formatting.
- One service module per domain (`listings`, `tours`, …); routes stay thin and call services.
- Structured JSON logs: `{ts, client_id, retell_call_id, tool, latency_ms, ok, reason}`. No PII in the message field.
- Return shapes are pydantic models, not raw dicts, so the contract with Retell is typed.
- Store UTC, speak client-local. Format numbers/dates for speech in the agent prompt, not the DB.

## 5. Security & secrets

- **Secrets never touch git.** `.env` and `secrets/` are gitignored. Only `.env.example` (empty keys) is committed.
- The moved file `secrets/twilio-recovery-code.txt` is a **credential** — treat it as one. Keep it in a password manager; if it was ever shared/committed anywhere, **rotate it**.
- Use the Supabase **service-role key** only on the server, never client-side.
- **Verify the Retell webhook signature** before trusting a payload.
- Enable **Row-Level Security** on Supabase before onboarding real clients (defense in depth on top of app-level `client_id` filtering).
- Never log full phone numbers, full transcripts, or keys. Redact.

## 6. Compliance baked into code

- **TCPA:** SMS sends are gated on `sms_consent == true`. No consent → no text, ever. Keep the flag on the `tour_bookings` row as the audit trail.
- **Recording disclosure** is in the greeting — don't remove it.
- **Fair Housing** is enforced in the agent prompt ([RETELL_AGENT_CONFIG.md](RETELL_AGENT_CONFIG.md) §"FAIR HOUSING"). Backend never stores or returns demographic/neighborhood judgments; if such a field ever appears in data, don't surface it.
- **Pilot minute cap:** enforce `minutes_cap` in the webhook when incrementing `minutes_used`. On breach, notify *us*, not the client's callers — never hard-cut a live caller.
- **Honesty:** the agent identifies as AI when asked. Don't "optimize" that away.

## 7. Testing rules

- **Curl-first:** every endpoint is verified with `curl` (scripts in `backend/tests/curl/`) **before** it's wired into Retell. The backend is provably correct without spending a voice minute.
- **The gauntlet is the gate.** Gate A = 9/10 consecutive adversarial calls end correctly (right tool, right data, clean confirmation, correct summary email). Log every failure → patch → rerun. Full 15-scenario list: [PROPTALK_US_BUILD_PLAYBOOK.md](PROPTALK_US_BUILD_PLAYBOOK.md) §6.1.
- Test the three dangerous paths explicitly: double-book attempt, unit-not-in-data ("must not invent"), emergency (< 60s escalation), fair-housing probe.

## 8. Vendor / region notes (Pakistan-based founders)

- **OpenPhone** and some US-only dialers have signup/verification friction from a +92 number. This is an **outreach-phase** tool (Phase 7), not a build blocker. Resolution options are in [phases.md](phases.md) Phase 7 — short version: have a US-based partner create it, or use **Twilio** (already in the stack, international-friendly) for a US caller ID.
- The real requirement for cold calling is a **US local caller ID**, not one specific vendor.
- Buy the **voice number inside Retell** — no separate US number needed for the agent itself.

## 9. Definition of done (per tool)

A tool is "done" when: typed request/response models exist · it filters by `client_id` · it returns < 1KB in < 800ms · it fails gracefully with a small JSON · it's covered by a curl script · every call is logged with latency. Only then attach it to Retell.
