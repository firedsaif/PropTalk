# PropTalk US — Build Phases

**Last updated:** 2026-07-15 · Doubles as the progress tracker — check boxes as you go. Companion to [prd.md](prd.md), [architecture.md](architecture.md), [rules.md](rules.md).

> **Sequencing principle (your constraint):** build and validate the *entire* product on **$0**, and push every paid tool as late as possible. Real money starts at outreach, not at build. The **Money timeline** at the bottom is the map.

---

## Phase 0 — Free foundation
**Goal:** everything you need to start building, all free. **Cost: $0.**
- [ ] Free accounts: GitHub, Supabase, Cal.com, Resend, Loom, Google Sheet (CRM).
- [ ] Retell account (use free credits — no top-up yet).
- [x] Local dev: Python 3.14 + `uvicorn` installed in `backend/.venv`. *(Tunnel deferred to Phase 3 — not needed until Retell calls your tools.)*
- [x] Repo initialized; `.env` created from `.env.example`; `secrets/` + `.env` confirmed out of git; foundation committed.
- [ ] Read [prd.md](prd.md) + [architecture.md](architecture.md) + [rules.md](rules.md) once.

**Exit:** ✅ FastAPI runs locally — `GET /health` → `{"status":"ok"}`. (Public tunnel URL comes in Phase 3.)

## Phase 1 — Data layer *(Playbook Day 1)* ✅ DONE
**Goal:** the database exists and the core query works. **Cost: $0.**
- [x] Schema applied to Supabase (`backend/sql/schema.sql`) — 6 tables + search index, us-east-1.
- [x] Willowbrook client + 8 listings seeded (`backend/sql/seed_willowbrook.sql`), incl. 1 leased decoy.
- [x] Listing search written + tested (`backend/app/services/listings.py` + `backend/scripts/test_search.py`) — 5 realistic filters return correct units; leased unit excluded.

**Exit:** ✅ search returns correct listings for realistic filters (verified 2026-07-14).

## Phase 2 — Backend + tools *(Playbook Day 2)* ✅ DONE
**Goal:** all six tools + webhook live locally, curl-verified. **Cost: $0.**
- [x] FastAPI app, `/health`, structured logging with latency (`app/logging.py`, `timed_tool`).
- [x] Implement the 6 `POST /tools/*` endpoints (typed pydantic models, `client_id` filtering, < 1KB responses).
- [x] Implement `POST /webhooks/retell` (stores transcript + Retell's own `call_analysis.call_summary`; email is a stubbed log line until Resend lands in Phase 4).
- [x] A curl script per endpoint in `tests/curl/`; every one passes (incl. idempotent retry + slot-conflict paths for `book_tour`, 404 for an unknown `client_id`, graceful `no_matches`/`not_available` payloads).

**Exit:** ✅ every tool works via curl (verified 2026-07-14). `check_tour_slots`/`book_tour` are Cal.com stubs (business-hours mock slots) until Phase 4 wires the real calendar - schema/idempotency already match the real shape. Connection pooling added (`get_pooled_connection`) since local dev is a transcontinental round trip to Supabase (Pakistan → us-east-1, ~700ms-1.3s per query even warmed) - the 800ms product budget is validated against a real deployment in Phase 5, not this dev machine.

## Phase 3 — The agent *(Playbook Day 3)* ✅ DONE
**Goal:** a real conversation end-to-end. **Cost: $0 (free Retell credits).**
- [x] Retell agent + LLM created **from code**, not the dashboard (`backend/scripts/retell_provision.py`) — the system prompt is read verbatim from [RETELL_AGENT_CONFIG.md](RETELL_AGENT_CONFIG.md), so no hand-paste typos. Model **gpt-4.1** (gpt-4o-mini was too weak at tool-calling — it hallucinated listings).
- [x] All 6 custom functions + webhook attached, pointing at a `cloudflared` tunnel URL. Re-point after a tunnel rotation with `retell_provision.py update-urls` (no recreation).
- [x] Voice: **11labs-Marissa** (warm American female) chosen from the ElevenLabs shortlist.
- [x] Tested with Retell **web calls** (no number purchased). Credit-safe method: every tool is proven with `tests/curl/run_all.sh` *through the tunnel* before any call, so voice minutes only test agent behavior.

**Exit:** ✅ a full web call qualified a renter (2-bed, $1800, pet, move-in ~2wk) → real Unit 2A @ $1795 → booked a tour (verified 2026-07-14).

**Bugs found via voice testing + fixed (all have curl regressions now):**
- `check_tour_slots`/`book_tour` took a raw UUID the LLM mangled → crash. Fix: short speakable **property codes** (`2A`, `PALM`) + property lookups never cast caller input to `::uuid` (bad input → clean `not_found`, not a 500).
- Agent passed a **2024** `move_in_by` (LLM doesn't know "today") → zero results. Fix: prompt now carries the real date via Retell `{{current_time_America/New_York}}`, and search ignores a past `move_in_by` instead of excluding everything.
- Agent called `book_tour` **twice** (once to record SMS consent captured after booking). Idempotency already prevented a duplicate row; fix: prompt now captures consent *before* a single booking call, and an idempotent re-call refreshes `sms_consent` so the latest consent wins (TCPA).
- Per-call latency: added an in-process **client cache** (`app/deps.py`) — halved tool latency in dev by removing a second DB round trip. Absolute latency is still dominated by the Pakistan→us-east-1 hop; that's a **Phase 5/6** concern (Railway US-East), not a code issue.

## Phase 4 — Tours + the money loop *(Playbook Days 4–5)* 🟡 CODE DONE — needs 2 free accounts
**Goal:** books real tours and sends the summary email. **Cost: $0.**
- [x] Cal.com client written (`app/services/calcom.py`, API v2) + `check_tour_slots`/`book_tour` wired to it (store UTC, speak local — verified: slot stored `14:00Z` → email says `10:00 AM EDT`).
- [x] Test: book, **reschedule**, **double-book attempt** — `tests/curl/reschedule_tour.sh` + `book_tour.sh`, both green.
- [x] Post-call summary from Retell `call_analyzed` (no extra LLM bill) → Resend email (`app/services/notify.py`).
- [x] Summary email built and previewed (`app/services/email_template.py`, 6 variants via `scripts/preview_summary_email.py`).
- [x] SMS still **off** (`FEATURE_SMS_ENABLED=false`) — preflight asserts it.
- [x] **Resend verified live** (2026-07-16): real summary email delivered from `onboarding@resend.dev`. Free tier only delivers to your own signup address until a domain is verified, so `clients.notify_email` is set to it directly in the DB — deliberately *not* in `seed_willowbrook.sql`, which is public. `apply_sql.py` won't clobber it (`on conflict do nothing`).
- [ ] **Cal.com blocked — not a code problem, a network one. See below.** Verify on the Phase 6 deploy.
- [ ] Then: one web call → summary email in the inbox (calendar half deferred with Cal.com).

**Exit:** a web call → booking on the calendar → summary email in the inbox. No spend yet.
*Amended 2026-07-16:* the email half is met. The calendar half moves to Phase 6 (below). Phase 5's gauntlet doesn't depend on Cal.com — it tests agent behaviour and latency against the business-hours fallback, so this is not a Gate A blocker.

> ### ⚠️ Cal.com is unreachable from the dev network (found 2026-07-16)
> Every request to `cal.com`/`api.cal.com` from here returns **403 with a Cloudflare "Just a moment..." challenge** — including *unauthenticated* requests and the plain homepage, while `api.resend.com` answers normally from the same machine. DNS and TLS are fine. So it's **not the API key** (`cal_live_`, correct shape) and not our code: Cloudflare is challenging non-browser clients from this network/region. A browser reaches `app.cal.com` fine because it silently solves the JS challenge; an API client can't, and defeating a bot challenge is not on the table.
>
> **Current state:** `CALCOM_API_KEY` is *commented out* in the root `.env` (value preserved, with a note). This matters: a **set** key makes `check_tour_slots` correctly return **no slots** — it won't invent times it can't book — which silently kills the demo. Commented out, tours use the business-hours generator and everything works.
>
> **What's unproven:** `app/services/calcom.py` is written from Cal.com's v2 docs but has **never seen a live response**. Treat its parsers as unverified until a real call proves them. Event type `6330414` ("Property Tour (30 min)") is configured and waiting.
>
> **To close it (Phase 6, on Railway US-East):** uncomment `CALCOM_API_KEY`, run `python scripts\test_integrations.py` **there** — a US server IP is very unlikely to be challenged. If it still is, Cal.com support can allowlist the key, and the fallback keeps the product shippable meanwhile.

**Design decisions worth remembering:**
- **DB first, calendar second.** The partial unique indexes on `tour_bookings` are what make double-booking impossible (atomic); Cal.com is a mirror. A booking whose Cal.com write fails is *kept* (the caller was told it's booked) with `cal_booking_id` null, and the summary email tells the PM to add it by hand — a loud, visible degrade instead of a silent lie.
- **No fake slots.** If Cal.com is unreachable, `check_tour_slots` returns empty rather than falling back to generated business hours — offering a time we can't book is the fabrication `rules.md §3` forbids. The generator survives only as the *no-account* path.
- **Reschedule needs no new tool.** The agent just calls `book_tour` again; the backend matches the same prospect (phone + same unit) and moves the tour, releasing the old slot. Only ever touches a booking made by that same phone number.
- **Cal.com needs an attendee email; phone callers don't have one.** We mint `notify_email +tour-<digits>` so the invite lands in the PM's own inbox. No change to the agent prompt or the 6 tool schemas.

**Known Phase 5 follow-ups (deliberate, not bugs):**
- `book_tour` now waits on a Cal.com round trip inside the voice path, so it will exceed the 800ms budget. That's the right trade (we must know the slot is really ours before the agent confirms) — Phase 5's "filler on slow tools" is the answer, not removing the check.
- Resend free tier only delivers to your own signup address until a domain is verified; `clients.notify_email` must be that address for now.

## Phase 5 — Latency + the gauntlet *(Playbook Days 6–8, Gate A)*
**Goal:** it's reliably good. **Cost: first real spend — ~$20 Retell top-up for test minutes if free credits are gone.**
- [ ] Tune endpointing/backchanneling until reply starts < 1.2s; add filler on slow tools.
- [ ] Run the 15-scenario gauntlet, 50 calls ([PROPTALK_US_BUILD_PLAYBOOK.md](PROPTALK_US_BUILD_PLAYBOOK.md) §6.1).
- [ ] Log every failure → patch prompt/tools daily → rerun.

**Exit — GATE A:** 9/10 consecutive adversarial calls end correctly. **No outreach until this passes.**

## Phase 6 — Go live for demos
**Goal:** a real number people can call, and demo assets. **Cost: ~$25–50 one-time/first-month.**
- [ ] Buy the voice number **inside Retell** (~$2/mo).
- [ ] Deploy backend to **Railway** hobby, US-East ($5/mo) — swap tunnel URL for the stable one in Retell.
- [ ] **Close out Phase 4's calendar half here:** uncomment `CALCOM_API_KEY` and run `python scripts\test_integrations.py` from the deploy — Cal.com is Cloudflare-challenged from the dev network (see Phase 4). First real exercise of `app/services/calcom.py`; budget time to fix its parsers against a live response.
- [ ] Record the 90-second Loom; build the one-page landing site (a free Vercel/Carrd subdomain is fine to start).
- [ ] Personalized-demo playbook ready (scrape a prospect's listings → new client + properties → their name in the greeting).

**Exit:** anyone can call the demo number and be impressed; Loom + landing page shippable.

## Phase 7 — Outreach infrastructure  ← **"the payment stuff" lands here**
**Goal:** the machine that reaches prospects. **Cost: ~$60/mo + domains.** This is where the recurring paid tools switch on.
- [ ] Buy main domain + 2 outreach domains; Google Workspace on the outreach domains; **email warmup ON** (14-day clock).
- [ ] **Instantly** (~$37/mo) — load the 3-email sequence (sending starts after warmup).
- [ ] **US caller ID for cold calls** — resolve the dialer (see decision box below).
- [ ] Fund **Twilio** (+$20) and flip `FEATURE_SMS_ENABLED=true` for pilot SMS confirmations.
- [ ] Lead list to 300+ rows; Facebook/BiggerPockets groups joined.

> **Dialer decision (OpenPhone from Pakistan):** OpenPhone provisions a US number for you, but its **signup/OTP verification and billing** are US/Canada-oriented and often reject a +92 number — so you don't need to *own* a US number first, you need to get *past verification*.
> - **Best:** if the Partner/Closer is US-based, they create the OpenPhone account. Cleanest path.
> - **If both founders are in Pakistan:** use **Twilio** (already in your stack, international-friendly signup) — buy a US local number and dial via a softphone/SIP client. Or a more international-friendly provider (Skype number, Zoom Phone, JustCall, Dialpad, Sonetel).
> - The requirement is a **US local caller ID**, not OpenPhone specifically. Don't let this vendor block outreach.

**Exit:** domains warm, sequences loaded, a working US-caller-ID dialer, SMS live.

## Phase 8 — First "yes" → money *(trigger-based, not date-based)*
**Goal:** get paid. **Cost: ~$600 one-time — only when 2–3 hot pilots exist.**
- [ ] Trigger on hot pilots: **Stripe Atlas** (Delaware LLC, ~$500; EIN takes 1–3 weeks).
- [ ] **Wise Business** (primary, Pakistan-friendly); apply to Mercury + Relay as free backups.
- [ ] Stripe subscription $399/mo, card on file, dunning on.
- [ ] 1-page month-to-month service agreement.
- [ ] Set aside ~$75/mo for DE franchise tax + US tax filing (Form 5472 — skipping = $25k penalty) + registered agent.

**Exit — GATES B & C:** ≥ 2 pilots live (~Day 45), ≥ 5 paying (~Day 90).

---

## Money timeline (the answer to "can we start with no money?")

**Yes.** Phases 0–4 are **$0**. Here's exactly when a dollar first leaves:

| Stage | Phases | Spend | Notes |
|---|---|---|---|
| **Build & validate** | 0–4 | **$0** | Free tiers + free Retell credits + local backend behind a tunnel. Backend proven with curl; agent proven with web calls; SMS off. |
| **Harden** | 5 | **~$0–20** | Only if free Retell credits run out mid-gauntlet — a ~$20 top-up buys plenty of test minutes. |
| **Go live for demos** | 6 | **~$25–50** | Retell number (~$2/mo) + Railway ($5/mo) + optional cheap domain. First recurring cost. |
| **Outreach** | 7 | **~$60/mo** | Instantly + Workspace + Twilio + dialer. **All the real "payment stuff" clusters here** — exactly where you wanted it. |
| **Incorporate & bill** | 8 | **~$600 one-time** | Only triggered by 2–3 hot pilots. LLC + banking + Stripe. |

So: build the whole product for essentially free, spend ~$20 to finish testing, ~$25–50 to switch on the demo line, and only take on the ~$60/mo outreach stack (and later the ~$600 incorporation) once the product is proven and prospects are lining up.
