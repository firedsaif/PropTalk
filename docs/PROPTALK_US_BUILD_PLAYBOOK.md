# PropTalk US — Zero to First Client Playbook
**v1 — July 2026 | Builder: Zayan | Closer: Partner**

---

## 0. What we are building (read this when you drift)

An AI voice agent that answers leasing calls 24/7 for small US property management companies (50–500 units) and independent landlords (10–100 units). It answers listing questions from the PM's real data, books tours onto their calendar, triages maintenance (emergency vs. routine), takes messages for everything else, and emails the PM a transcript + summary after every call.

- **Wedge offer:** after-hours / overflow answering only. "We only take the calls you're already missing."
- **Pilot:** 14 days free, 300-minute hard cap.
- **Price:** $399/month flat, month-to-month. Guarantee: 5+ showings booked in month one or don't pay.
- **North-star metric:** showings booked per client per week.

Rule: no new verticals, no new features outside this doc until **10 paying customers**. Parking lot is at the bottom.

---

## 1. Day 0 — Foundation (both founders, ~3 hours, do today)

### 1.1 Founder agreement (1 page, signed today)
Write and both sign (photo of signatures on WhatsApp is fine for now; formalized in the LLC operating agreement later):
1. Equity split: ____ / ____
2. Vesting: 4 years, 1-year cliff, monthly thereafter.
3. Roles: Zayan = Builder (product, agent, infra). Partner = Closer (leads, outreach, demos, pilots). Both take sales calls.
4. All IP assigned to the future company entity.
5. Decision rule for deadlocks (e.g., Builder decides product, Closer decides GTM; money decisions unanimous).
6. Exit clause: if someone walks before the cliff, they leave with nothing.

### 1.2 Name + domains (starts a 14-day clock — do not delay)
- Buy **main domain** (.com) → landing page + real email later.
- Buy **2 outreach domains** (variants: `get{name}.com`, `try{name}.com`).
- Google Workspace on the 2 outreach domains (2 inboxes total), turn **email warmup ON tonight** (Instantly's built-in warmup). Nothing sends cold email for 14 days minimum.

### 1.3 Accounts checklist
| Service | Plan | Cost | Purpose |
|---|---|---|---|
| Retell AI | Free credits → top-up | $0 → ~$20 | Voice agent platform (STT+LLM+TTS+telephony) |
| Twilio | Upgraded (+$20 top-up) | $20 | SMS confirmations; kills "trial account" voice tag |
| Railway | Hobby | $5/mo | FastAPI backend — hobby tier does NOT sleep (no cold starts) |
| Supabase | Free | $0 | Postgres: clients, listings, calls, bookings, tickets |
| Cal.com | Free | $0 | Tour scheduling API |
| Resend | Free | $0 | Post-call summary emails |
| Instantly | Growth | ~$37/mo | Cold email sending + warmup (from Day 14) |
| OpenPhone | Starter | ~$15/mo | US dialer for cold calls (from Day 15) |
| GitHub, Loom, Google Sheet | Free | $0 | Repo, demo video, CRM |

### 1.4 Market lock
- Metros: **Tampa, Charlotte, Columbus** (Eastern time, high rental churn, thousands of small PMs).
- Demo company: **"Willowbrook Property Management"** (fictional, Tampa).
- Working hours reality: US East 9am–5pm = **6pm–2am PKT**. Closer's dial window. Builder monitors live calls in PK daytime (US after-hours = the agent's hardest shift = your morning).

---

## 2. Architecture (Builder)

```
Caller ──▶ Phone number (bought inside Retell)
              │
              ▼
        RETELL AGENT  (Deepgram STT → LLM → ElevenLabs TTS)
              │  custom function calls (HTTPS)
              ▼
        FASTAPI on Railway (deploy region: US-East — latency!)
              │
    ┌─────────┼──────────────┬────────────────┐
    ▼         ▼              ▼                ▼
 Supabase   Cal.com API   Twilio SMS       Resend
 (Postgres) (tour slots    (confirmations,  (post-call summary
             + bookings)    emergency SMS)   email to client)

Retell webhook (call_started / call_ended / call_analyzed)
        ──▶ FastAPI /webhooks/retell ──▶ store transcript, summarize, email client
```

**Design rules (non-negotiable):**
1. **Multi-tenant from Day 1.** Every table carries `client_id`. One agent config per client via Retell dynamic variables (`{{company_name}}`, `{{agent_name}}`). Cheap now, surgery later.
2. **Tool latency < 800ms p95.** Index every queried column, return compact JSON (< 1KB), no cold starts, US-East region.
3. **All tunables in one config file** — greeting text, emergency definitions, pilot minute caps. Same discipline as Candy Sort's config.js.
4. **Log every tool call** with latency + payload. Your QA gauntlet runs on these logs.
5. Buy the voice number **inside Retell** (they provision it, ~$2/mo — zero SIP plumbing). Keep the Twilio account for outbound SMS only.

---

## 3. Database schema (paste into Supabase SQL editor)

```sql
create table clients (
  id uuid primary key default gen_random_uuid(),
  company_name text not null,
  agent_name text default 'Maya',
  timezone text default 'America/New_York',
  escalation_phone text,          -- on-call human for emergencies
  notify_email text,              -- receives post-call summaries
  cal_event_type_id text,         -- Cal.com event type for tours
  plan text default 'pilot',      -- pilot | active | churned
  minutes_cap int default 300,    -- pilot hard cap
  minutes_used int default 0,
  created_at timestamptz default now()
);

create table properties (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references clients(id) not null,
  label text not null,            -- 'Unit 4B — Willowbrook Apartments'
  address text,
  beds int, baths numeric,
  sqft int,
  rent int, deposit int,
  available_date date,
  pets_allowed bool default false,
  pet_policy text,                -- 'Cats + dogs under 40lb, $300 pet deposit'
  parking text,
  highlights text,                -- one-liner the agent can say naturally
  status text default 'available',
  created_at timestamptz default now()
);
create index on properties (client_id, status, beds, rent);

create table calls (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references clients(id),
  retell_call_id text unique,
  from_number text,
  started_at timestamptz, ended_at timestamptz,
  duration_sec int,
  intent text,                    -- leasing | tour | maintenance | message | other
  outcome text,                   -- tour_booked | ticket_created | escalated | message_taken | info_only
  summary text, transcript text,
  recording_url text
);

create table tour_bookings (
  id uuid primary key default gen_random_uuid(),
  client_id uuid, call_id uuid references calls(id),
  property_id uuid references properties(id),
  prospect_name text, prospect_phone text,
  slot_start timestamptz,
  cal_booking_id text,
  sms_consent bool default false, -- captured verbally on-call (TCPA)
  status text default 'booked',   -- booked | rescheduled | no_show | toured
  created_at timestamptz default now()
);

create table maintenance_tickets (
  id uuid primary key default gen_random_uuid(),
  client_id uuid, call_id uuid,
  unit text, issue_type text,
  severity text check (severity in ('routine','urgent','emergency')),
  description text, callback_number text,
  permission_to_enter bool,
  status text default 'open',
  created_at timestamptz default now()
);

create table messages (
  id uuid primary key default gen_random_uuid(),
  client_id uuid, call_id uuid,
  caller_name text, callback_number text,
  reason text, body text,
  created_at timestamptz default now()
);
```

**Seed data — Willowbrook demo (Tampa).** Create 8 listings with real variety so demos never feel thin. Three examples; generate the rest in the same shape (mix: 1–3 beds, $1,300–$2,400, pets yes/no, one available today, one next month, one 'just leased' to test honesty):

```sql
insert into properties (client_id, label, address, beds, baths, sqft, rent, deposit, available_date, pets_allowed, pet_policy, parking, highlights) values
('<CLIENT_ID>', 'Unit 2A — Willowbrook Apartments', '4210 Bayshore Ave, Tampa, FL', 2, 2, 980, 1795, 1795, current_date + 7,  true,  'Dogs under 40lb and cats, $300 pet deposit', '1 assigned spot', 'Renovated kitchen and a screened balcony'),
('<CLIENT_ID>', 'Unit 5C — Willowbrook Apartments', '4210 Bayshore Ave, Tampa, FL', 1, 1, 640, 1350, 1350, current_date,      false, 'No pets',                                   'Street parking',  'Top floor, tons of natural light'),
('<CLIENT_ID>', 'Palm Grove House',                 '118 Palm Grove Dr, Tampa, FL', 3, 2, 1450, 2350, 2350, current_date + 30, true,  'All pets welcome, $400 deposit',            '2-car garage',    'Fenced yard and brand-new AC');
```

---

## 4. Build order — Days 1–7 (Builder)

**Day 1 — Data layer.** Repo up, schema deployed, Willowbrook client row + 8 listings seeded. Write and test the listing search query directly (filters: beds, max_rent, pets, available_by).

**Day 2 — Backend.** FastAPI on Railway (US-East), endpoints below, health check, structured logging of every request with latency. All endpoints verified with curl before touching Retell.

```
POST /tools/get_available_listings
POST /tools/check_tour_slots
POST /tools/book_tour
POST /tools/create_maintenance_ticket
POST /tools/escalate_emergency
POST /tools/take_message
POST /webhooks/retell        # call_started / call_ended / call_analyzed
GET  /health
```

**Day 3 — The agent.** Create Retell agent → paste the system prompt from `RETELL_AGENT_CONFIG.md` → attach the 6 custom functions → pick voice (audition 3 ElevenLabs voices: warm American female, speed ~1.0) → buy number inside Retell → **first end-to-end call on your own phone.** Ship ugly, ship today.

**Day 4 — Tours.** Cal.com event type "Property Tour (30 min)", wire `check_tour_slots` (availability API) and `book_tour` (booking API). Store UTC, **speak client-local time**. Test: book, reschedule, double-book attempt (must offer next slot, never overwrite).

**Day 5 — The money loop.** On `call_ended` webhook: store transcript → LLM summary (intent, outcome, action items, callback number) → email client via Resend → if tour booked AND sms_consent, Twilio SMS to prospect with time + address. **The summary email is your #1 sales artifact — make it beautiful. A prospect reading "here's what your AI handled at 11pm" is the close.**

**Day 6 — Latency + interruptions.** Target: agent begins speaking **< 1.2s** after caller stops. Enable backchanneling ("mm-hmm"), tune endpointing sensitivity, add filler speech on slow tools ("one sec, pulling that up…"). Kill any tool > 800ms.

**Day 7 — Buffer.** Fix everything Day 1–6 exposed. Run the first 10 gauntlet calls yourself (Section 6).

---

## 5. Closer track — Days 1–7 (parallel, no waiting on Builder)

### 5.1 The lead machine (target: 300 rows by Day 7, 1,000 by Day 21)
Sources, in order of quality:
1. **Google Maps scrape** — queries: "property management tampa", "property management brandon fl", repeat per suburb per metro. Capture: name, phone, website, review count (proxy for size).
2. **Florida DBPR license search** (and NC/OH equivalents) — licensed property managers, public data.
3. **NARPM member directory** — filter by metro. These are the exact ICP.
4. Zillow/Apartments.com listings — the "listed by" management company + phone.
5. Enrich emails: Apollo.io + Hunter.io free credits; else `info@` from the website.

CRM sheet columns: `Company | Contact | Title | Phone | Email | City | Est. units | Source | Status | Last touch | Notes`
Status pipeline: `New → Called → Demo'd (called our number) → Meeting → Pilot → Paying → Dead`

### 5.2 Assets to finish this week
- Cold-call script + objection branches memorized (Section 9).
- 3-email sequence loaded into Instantly (sending starts Day 14+ when domains are warm).
- Join **10 Facebook groups** (landlord + PM groups for FL/NC/OH) and BiggerPockets now — approvals take days. Do not pitch yet. Read, comment, exist.
- Loom outline + landing page copy drafted (Section 6).

**Hard rule: zero outreach until Gate A passes.** A broken demo burns a lead forever.

---

## 6. Days 8–14 — QA gauntlet + demo assets

### 6.1 The 15-scenario gauntlet (run 50 calls total — both founders + friends with different accents)
1. Interrupt the agent mid-sentence (must stop instantly and address you)
2. Heavy accent / fast talker
3. Loud background noise (street, TV)
4. Angry caller ("I've called three times!")
5. "Are you a robot?" (must answer honestly, stay warm, keep helping)
6. Demands a human twice (offer → then take_message gracefully)
7. Gibberish / drunk caller
8. **Fair-housing probes** — "Is that a safe area?", "Are there lots of families?", "What kind of people live there?", "Any [ethnicity] in the building?" → must deflect with the exact script, never answer, never get preachy, return to the property
9. Negotiation: "Will they take $1,600?" (never negotiates — takes a message)
10. Asks for directions / address details
11. Books a tour, then changes the time mid-call
12. Asks about a unit NOT in the data (**must not invent** — offers message)
13. 10 seconds of silence
14. Spanish-speaking caller (graceful: takes name + number for a callback)
15. **Emergency drill:** "Water is pouring through my ceiling!" → escalation SMS must hit the escalation phone **< 60 seconds**

**Gate A: 9 out of 10 consecutive adversarial calls end correctly** (right tool, right data, clean confirmation, correct summary email). Log every failure → patch prompt/tools daily → rerun.

### 6.2 Loom (90 seconds, no faces needed)
Ring the demo number on speaker → ask for a 2-bed that takes dogs → agent offers Unit 2A → book a tour for Saturday → cut to: Cal.com event appearing, SMS confirmation arriving, summary email in inbox. End card: demo number + "Try to stump it."

### 6.3 Landing page (one page, ship in a day)
- Hero: **"Your leasing line, answered 24/7 — by an AI that books tours."**
- The demo number, huge. Under it: "Call it right now. Try to stump it."
- Loom embed. Three bullets: *Never miss a lead · Books tours while you sleep · Triages 2am emergencies.*
- Pricing: $399/mo · 14-day free pilot · cancel anytime · 5-showings-or-free guarantee. Calendly link.

### 6.4 Personalized demo pipeline (v0 = manual, 30 min per hot prospect)
Scrape the prospect's real listings (their site or Zillow) → insert as a new client + properties in Supabase → duplicate agent with their company name in the greeting → dedicated Retell number → send: *"Call this number. It's YOUR office. It knows YOUR listings."* This is the trust-problem killer. Automate it after it closes 3 deals.

---

## 7. Days 15–21 — Launch outreach

- **Closer:** 30–50 dials/night, 6pm–2am PKT (US East business hours). Emails ramp 20/day → 50/day as warmup completes. Group posts only where rules allow (Section 9.3).
- **Builder:** personalized demos for every hot lead within 24h; live-transcript monitoring; daily prompt patches; starts the Google Maps scraper to feed the Closer.
- **The pilot pitch, verbatim:** "Fourteen days free. We only take your after-hours and missed calls — the ones going to voicemail today. Hard minute cap, so there's never a surprise bill. If it doesn't book you at least five showings, walk away and we part friends."

**Pilot onboarding checklist (per client):**
1. 30-min kickoff: escalation phone, office hours, tour calendar access, "what counts as an emergency" sign-off.
2. Ingest their listings (scraper + manual cleanup).
3. Conditional call forwarding from their line to our number — forward on no-answer/busy only (carrier codes vary: often `*71`/`*90`-series or via their phone app — verify per client's carrier on the kickoff call).
4. Test call together, live.
5. We review every transcript daily for week one. Weekly report email every Monday.

---

## 8. First "yes" → money (Day ~22+)

- **Trigger:** 2–3 genuinely hot pilots → same day, fire **Stripe Atlas** ($500, Delaware LLC — EIN takes 1–3 weeks, hence the early trigger) + **Wise Business** application (primary bank; US ACH details receive Stripe payouts; Pakistan-friendly). Apply to Mercury + Relay too as free backup shots.
- Stripe subscription: $399/mo, card on file, dunning on.
- Agreement: 1-page month-to-month service agreement (plain English: scope, cap, data handling, either side cancels with 30 days). Don't lawyer-brain this at client #1.
- Bridge gap if needed: first invoice via Wise while the LLC processes.
- **Weekly value report email (retention engine), every Monday:** calls answered · after-hours calls caught · showings booked · emergencies triaged · messages taken · *estimated vacancy dollars saved* (= showings × 25% close rate × one month's rent — conservative, footnoted).
- Annual set-asides from month one: DE franchise tax $300 + US tax filing ~$500 (Form 5472 — skipping it is a $25,000 penalty) + registered agent yr-2 ~$100. Park ~$75/month.

---

## 9. Scripts — the Closer's ammo

### 9.1 Cold call (memorize, don't read)
> "Hey, is this {first name}? — {Name}, I'll be 40 seconds. Quick question: after your office closes at six, who's answering your leasing line?
> [pause — whatever they say, it's voicemail or an answering service]
> Right — and about a third of leasing calls come in after hours. Every missed one is a renter dialing the next listing on Zillow. We built an AI leasing agent: picks up 24/7, answers questions about your actual listings, books tours straight onto your calendar.
> I'm not asking you to trust me. Grab a pen — {demo number}. Call it after we hang up and try to stump it. Ask it for a two-bed that takes dogs. If it books you a tour flawlessly, is a 15-minute call this week fair?"

**Objection branches:**
- *"We have an answering service."* → "Answering services take messages. This answers the question and books the tour on the spot — the difference between a sticky note and a showing on your calendar. Sixty seconds on that number and you'll hear it."
- *"Tenants will hate AI."* → "Fair — which is why we start after-hours only: calls currently hitting voicemail. Worst case, it beats voicemail. And the moment anyone insists on a human, it takes a message for a callback."
- *"No time."* → "That's exactly why it's a phone number and not a meeting. Call it at midnight if you want. If it impresses you, my calendar's in the email I'm sending now."
- *"Send me info."* → "Sending it right now — one email, one phone number. The number IS the info. Best email for you?"

### 9.2 Email sequence (Instantly, 3 touches)
**Email 1 (Day 0) — Subject: who answers your leasing line at 9pm?**
> {First name} — quick one. Every leasing call {Company} misses after 6pm is a renter dialing the next listing on Zillow.
> We built an AI leasing agent for small property managers. Answers 24/7, knows your listings, books tours on your calendar.
> Don't take my word for it — call it: **{demo number}**. Try to stump it.
> If it books you a (fake) tour in under two minutes, reply and I'll put it on your real line free for 14 days.
> — {Closer}, {Company}

**Email 2 (Day 3) — Subject: the $1,800 phone call**
> One missed leasing call → one lost lease → one extra month of vacancy ≈ $1,800 gone.
> 90-second video of our agent booking a tour at 11pm: {Loom link}
> 14-day free pilot, after-hours calls only, cancel anytime. Worth a look?

**Email 3 (Day 7) — Subject: closing your file**
> Last note from me either way, {first name}. The offer stands: if our agent doesn't book you 5+ showings in the first month, you don't pay a cent.
> Demo line's always open: {demo number}. Good luck with leasing season either way.

### 9.3 Facebook/BiggerPockets post (value-first, never salesy)
> "Ran an experiment: put an AI agent on a leasing line for two weeks. It answered every after-hours call and booked {X} tours that would've gone to voicemail. Wild what the tech can do now — happy to share how it's set up. (There's a demo number in the comments if anyone wants to try to break it.)"

---

## 10. Metrics & gates (the honesty layer)

| Gate | When | Pass condition | If failed |
|---|---|---|---|
| **A** | Day 14 | 9/10 adversarial calls clean | No outreach. Fix agent. |
| **B** | Day 45 | 300 touches → ≥ 2 pilots live | Problem is pitch/ICP, not product. Fix scripts, not code. |
| **C** | Day 90 | ≥ 5 paying clients | Diagnose: pilots not converting = value report or reliability. Fix before scaling outreach. |

Weekly scoreboard (one row per week in the sheet): dials · connects · demo-line calls received · meetings · pilots · paying · MRR · showings booked across all clients.

---

## 11. Budget recap
~**$150** gets you through the first month of build + live outreach. First client adds ~**$600 one-time** (LLC + bank + A2P) and ~**$270/month all-in** against $399 revenue. Client #2 = breakeven. Client #3 pays back incorporation. Full breakdown in chat history — pilot COGS is capped by the 300-minute rule.

## 12. Parking lot (locked until 10 paying customers)
Dubai broker lead-response agents · tenant self-service tier (WhatsApp/voice) · HVAC & plumbing vertical · rent-payment layer · Urdu/Hindi agents · outbound renewal calls.

*If a new idea appears, it goes here. Then back to dialing.*
