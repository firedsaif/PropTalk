# PropTalk US — Architecture

**Last updated:** 2026-07-13 · Companion to [prd.md](prd.md), [rules.md](rules.md), [phases.md](phases.md).

---

## 1. System context

```
Caller ──▶ Phone number (provisioned inside Retell)
              │
              ▼
        RETELL AGENT   (Deepgram STT → LLM → ElevenLabs TTS)
              │  custom function calls (HTTPS)
              ▼
        FASTAPI backend  (dev: local + tunnel · prod: Railway US-East)
              │
    ┌─────────┼───────────────┬──────────────────┐
    ▼         ▼               ▼                  ▼
 Supabase   Cal.com API    Twilio             Resend
 (Postgres) (slots +       (SMS + emergency   (post-call
             bookings)      call — deferred)   summary email)

Retell webhook (call_started / call_ended / call_analyzed)
        ──▶ FastAPI /webhooks/retell ──▶ store transcript, summarize, email client
```

Latency is the product. Keep the backend in **US-East**, index every queried column, return < 1KB JSON, and never sleep in production.

---

## 2. Tech stack

| Layer | Choice | Why | Cost posture |
|---|---|---|---|
| Voice platform | **Retell AI** | Bundles STT+LLM+TTS+telephony; buy the number inside it (no SIP plumbing) | Free credits → ~$20 top-up for test minutes |
| STT / TTS | Deepgram / ElevenLabs (via Retell) | Fast, natural | Included in Retell per-minute |
| Agent LLM | Fastest realtime GPT-4.1/4o-mini-class Retell offers | Latency beats brains here; the prompt carries the intelligence | Included in Retell per-minute |
| Backend | **FastAPI** (Python 3.11+), async | Simple, fast, great for JSON tools + webhooks | Free (local); $5/mo Railway later |
| Hosting (dev) | **Local `uvicorn` + tunnel** (ngrok/cloudflared) | Public HTTPS URL for Retell with zero hosting cost | Free |
| Hosting (prod) | **Railway** hobby, US-East | Hobby tier does **not** sleep — no cold starts | $5/mo (Phase 6) |
| Database | **Supabase** (Postgres) | Free tier, SQL, multi-tenant friendly | Free |
| Scheduling | **Cal.com** API | Free tour slots + booking API | Free |
| Email | **Resend** | Clean transactional email for summaries | Free tier |
| SMS + emergency call | **Twilio** | Confirmations + on-call alerts | Deferred; feature-flagged off until funded |
| Post-call summary | **Retell `call_analyzed`** first, own LLM pass later | Avoids a second LLM bill and extra latency early on | Free to start |
| Repo / demo / CRM | GitHub / Loom / Google Sheet | — | Free |

> **Free-first substitutions** (see [phases.md](phases.md)): run the backend locally behind a tunnel instead of Railway; test tools with `curl` and the agent with Retell **web calls** before buying a phone number; use Retell's built-in post-call analysis for the summary before wiring your own LLM; keep SMS off (`FEATURE_SMS_ENABLED=false`) until Twilio is funded — the summary email carries the value story on its own.

---

## 3. Data model

Canonical schema is in [PROPTALK_US_BUILD_PLAYBOOK.md](PROPTALK_US_BUILD_PLAYBOOK.md) §3 (paste into Supabase). Tables:

- `clients` — one row per PM (company, agent name, timezone, escalation phone, notify email, Cal event type, plan, `minutes_cap`, `minutes_used`).
- `properties` — units (beds, baths, rent, deposit, availability, pets, highlights, status). Index: `(client_id, status, beds, rent)`.
- `calls` — one row per call (retell_call_id, intent, outcome, summary, transcript, recording_url).
- `tour_bookings` — bookings (property, prospect, slot, cal_booking_id, `sms_consent`, status).
- `maintenance_tickets` — routine issues (unit, issue_type, severity, permission_to_enter).
- `messages` — everything else (caller, callback, reason, body).

**Every table carries `client_id`.** Multi-tenancy is structural, not bolted on. Enable Supabase Row-Level Security before onboarding real clients (see [rules.md](rules.md)).

---

## 4. API surface

```
POST /tools/get_available_listings     # returns ≤ 3 listings, compact fields only
POST /tools/check_tour_slots
POST /tools/book_tour
POST /tools/create_maintenance_ticket
POST /tools/escalate_emergency
POST /tools/take_message
POST /webhooks/retell                  # call_started / call_ended / call_analyzed
GET  /health
```

Request/response schemas per tool: [RETELL_AGENT_CONFIG.md](RETELL_AGENT_CONFIG.md) §C.
`get_available_listings` returns only: `property_id, label, beds, baths, rent, available_date, pets_allowed, pet_policy, highlights, address`.

---

## 5. Key request flows

**Leasing call → tour booked**
1. Retell calls `get_available_listings` with known filters → backend queries Postgres (indexed) → returns ≤ 3 compact matches.
2. Agent offers 1–2 → caller picks one → Retell calls `check_tour_slots(property_id)` → backend hits Cal.com availability.
3. Agent reads back name + number, confirms slot aloud → Retell calls `book_tour` → backend books via Cal.com, writes `tour_bookings`, returns confirmation.
4. Call ends → Retell fires `/webhooks/retell` → backend stores transcript, generates summary, emails the client, (optionally) SMSes the prospect if `sms_consent`.

**Emergency**
`escalate_emergency` → backend fires SMS + call to the client's `escalation_phone` (target < 60s). Fire-and-return fast; do the notify work without blocking the agent's spoken confirmation.

**Time handling:** store everything **UTC**, speak **client-local** time (`clients.timezone`).

---

## 6. Repo / file structure

```
US/                              # repo root
├── README.md
├── .gitignore
├── .env.example                 # copy to .env (gitignored) and fill
├── docs/
│   ├── prd.md · architecture.md · rules.md · phases.md
│   ├── PROPTALK_US_BUILD_PLAYBOOK.md
│   └── RETELL_AGENT_CONFIG.md
├── secrets/                     # gitignored — never committed
│   └── twilio-recovery-code.txt
├── backend/                     # FastAPI app (built in Phase 2)
│   ├── app/
│   │   ├── main.py              # app + router registration + /health
│   │   ├── settings.py          # env/secret loading (pydantic-settings)
│   │   ├── config.py            # ALL tunables: greeting, emergency defs, caps
│   │   ├── db.py                # Supabase/Postgres client
│   │   ├── logging.py           # structured logging w/ per-call latency
│   │   ├── deps.py              # client resolution by client_id
│   │   ├── models/              # pydantic request/response schemas per tool
│   │   ├── routes/
│   │   │   ├── tools.py         # the 6 POST /tools/* endpoints
│   │   │   └── webhooks.py      # POST /webhooks/retell
│   │   └── services/
│   │       ├── listings.py      # search query
│   │       ├── tours.py         # Cal.com integration
│   │       ├── maintenance.py · messages.py · escalation.py
│   │       ├── summary.py       # Retell analysis → (later) own LLM
│   │       └── notify.py        # Resend email + Twilio SMS
│   ├── sql/
│   │   ├── schema.sql           # from the playbook §3
│   │   └── seed_willowbrook.sql # demo client + 8 listings
│   ├── tests/curl/              # one script per endpoint (curl-first testing)
│   ├── requirements.txt
│   └── railway.json             # prod deploy config (Phase 6+)
├── landing/                     # one-page site (Phase 6)
└── ops/
    ├── crm.md                   # pointer to the Google Sheet
    └── runbook.md               # daily QA / transcript-review process
```

Only `docs/` and `secrets/` exist today. `backend/`, `landing/`, `ops/` are created as their phases begin — this tree is the target, not a claim they exist yet.

---

## 7. Environments

| | Dev | Prod |
|---|---|---|
| Backend | `uvicorn app.main:app --reload` on localhost | Railway, US-East, no sleep |
| Public URL | ngrok/cloudflared tunnel (update Retell URLs when it changes) | stable Railway domain |
| Agent testing | Retell **web call** + `curl` against tools | real phone number provisioned in Retell |
| Secrets | `.env` (gitignored) | Railway environment variables |

**Config discipline:** everything tunable (greeting text, emergency definitions, minute caps, per-client toggles) lives in `app/config.py` + `clients` rows — never hardcoded in handlers. Per-client agent differences ride on Retell **dynamic variables** (`{{company_name}}`, `{{agent_name}}`, `{{office_hours}}`), not duplicated agents.
