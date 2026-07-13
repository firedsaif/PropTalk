# PropTalk US — Build Phases

**Last updated:** 2026-07-13 · Doubles as the progress tracker — check boxes as you go. Companion to [prd.md](prd.md), [architecture.md](architecture.md), [rules.md](rules.md).

> **Sequencing principle (your constraint):** build and validate the *entire* product on **$0**, and push every paid tool as late as possible. Real money starts at outreach, not at build. The **Money timeline** at the bottom is the map.

---

## Phase 0 — Free foundation
**Goal:** everything you need to start building, all free. **Cost: $0.**
- [ ] Free accounts: GitHub, Supabase, Cal.com, Resend, Loom, Google Sheet (CRM).
- [ ] Retell account (use free credits — no top-up yet).
- [ ] Local dev: Python 3.11+, `uvicorn`, a tunnel (ngrok or cloudflared — free).
- [ ] Repo initialized; `.env` from `.env.example`; secrets stay out of git.
- [ ] Read [prd.md](prd.md) + [architecture.md](architecture.md) + [rules.md](rules.md) once.

**Exit:** you can run "hello world" FastAPI locally and hit it through the tunnel URL.

## Phase 1 — Data layer *(Playbook Day 1)*
**Goal:** the database exists and the core query works. **Cost: $0.**
- [ ] Paste `schema.sql` into Supabase (all six tables, indexes).
- [ ] Seed Willowbrook client row + 8 varied listings (`seed_willowbrook.sql`).
- [ ] Write + test the listing search query directly (beds / max_rent / pets / available_by).

**Exit:** search returns correct listings for realistic filters.

## Phase 2 — Backend + tools *(Playbook Day 2)*
**Goal:** all six tools + webhook live locally, curl-verified. **Cost: $0.**
- [ ] FastAPI app, `/health`, structured logging with latency.
- [ ] Implement the 6 `POST /tools/*` endpoints (typed models, `client_id` filtering, < 1KB responses).
- [ ] Implement `POST /webhooks/retell` (store transcript; summary + email stubbed for now).
- [ ] A curl script per endpoint in `tests/curl/`; every one passes.

**Exit:** every tool works via curl, under 800ms, without Retell.

## Phase 3 — The agent *(Playbook Day 3)*
**Goal:** a real conversation end-to-end. **Cost: $0 (free Retell credits; ~$20 top-up only if they run low).**
- [ ] Create the Retell agent; paste the system prompt from [RETELL_AGENT_CONFIG.md](RETELL_AGENT_CONFIG.md).
- [ ] Attach the 6 custom functions pointing at your **tunnel URL**.
- [ ] Audition 3 ElevenLabs voices; pick the least "IVR."
- [ ] Test with Retell **web calls** (no phone number purchase yet).

**Exit:** a full web call qualifies a renter and reaches the booking step correctly.

## Phase 4 — Tours + the money loop *(Playbook Days 4–5)*
**Goal:** books real tours and sends the summary email. **Cost: $0.**
- [ ] Cal.com event type "Property Tour (30 min)"; wire `check_tour_slots` + `book_tour` (store UTC, speak local).
- [ ] Test: book, reschedule, **double-book attempt** (must offer next slot, never overwrite).
- [ ] Post-call: generate summary (use Retell `call_analyzed` — no extra LLM bill) → email via Resend.
- [ ] Make the summary email **beautiful** — it's the #1 sales artifact.
- [ ] Keep SMS **off** (`FEATURE_SMS_ENABLED=false`) — Twilio deferred; the email carries the value.

**Exit:** a web call → booking on the calendar → summary email in the inbox. No spend yet.

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
