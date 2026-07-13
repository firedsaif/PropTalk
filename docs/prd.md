# PropTalk US — Product Requirements Document (PRD)

**Owner:** Zayan (Builder) · **Partner:** Closer · **Status:** Pre-build · **Last updated:** 2026-07-13

> This PRD is the "what" and "why." The "how" lives in [architecture.md](architecture.md), the "rules of the road" in [rules.md](rules.md), and the "in what order" in [phases.md](phases.md). Source material: [PROPTALK_US_BUILD_PLAYBOOK.md](PROPTALK_US_BUILD_PLAYBOOK.md) and [RETELL_AGENT_CONFIG.md](RETELL_AGENT_CONFIG.md).

---

## 1. Problem

Small US property managers (10–500 units) miss a large share of leasing calls — after hours, during showings, while on other lines. Roughly a third of leasing calls arrive after the office closes at 6pm. Every missed call is a renter dialing the next listing on Zillow. Voicemail and generic answering services don't recover the lead: they take a message, they don't answer the question or book the tour.

## 2. Solution

An AI voice agent that answers the leasing line 24/7 and:
- Answers listing questions from the PM's **real** data (rent, beds, pets, availability, deposits).
- Books tours directly onto the PM's calendar.
- Triages maintenance (emergency vs. routine) and alerts an on-call human for true emergencies.
- Takes a message for anything else.
- Emails the PM a transcript + summary after every call.

**Wedge:** after-hours / overflow only — "We only take the calls you're already missing."

## 3. Goals & non-goals

### Goals (v1)
- Recover after-hours and overflow leasing leads that currently die in voicemail.
- Book tours autonomously with correct times on the client's calendar.
- Never invent property facts; never violate fair-housing rules; escalate real emergencies fast.
- Be demonstrably better than voicemail from the first call — the demo number *is* the sales pitch.

### Non-goals (v1 — locked until 10 paying clients)
- No new verticals (HVAC, brokers, tenant self-service).
- No rent-payment layer, no outbound renewal calls, no multi-language agents.
- No negotiation, no application approvals, no legal/financial advice.
- Full parking lot in [PROPTALK_US_BUILD_PLAYBOOK.md](PROPTALK_US_BUILD_PLAYBOOK.md) §12.

## 4. Target users (ICP)

| | |
|---|---|
| **Primary buyer** | Owner/operator of a small PM company (50–500 units) or independent landlord (10–100 units) |
| **Metros (launch)** | Tampa, Charlotte, Columbus (Eastern time, high rental churn) |
| **End caller** | A prospective renter calling about a listing, or a tenant with a maintenance issue |
| **Operators** | Zayan (Builder — runs the agent/infra), Partner (Closer — sells, onboards) |

## 5. Core flows

### 5.1 Caller-facing (the agent's job)
1. **Leasing inquiry** → qualify (beds, budget, move-in, pets) → search real listings → offer best 1–2 → offer a tour.
2. **Book a tour** → check real slots → collect name + phone (read back) → confirm aloud → book → optional SMS confirmation (consent-gated).
3. **Maintenance** → collect unit/issue/callback → classify severity → emergency = escalate to on-call within 60s; routine = create ticket.
4. **Everything else** → take a message, promise a callback within one business day.

Full agent behavior spec (system prompt, tasks, fair-housing rules) lives in [RETELL_AGENT_CONFIG.md](RETELL_AGENT_CONFIG.md).

### 5.2 Client-facing (the PM's experience)
- After every call: an outcome-first summary email ("Tour booked — Sat 2:30pm — Unit 2A").
- Every Monday: a value report (calls answered, after-hours caught, showings booked, emergencies triaged, estimated vacancy dollars saved).

### 5.3 Operator-facing (us)
- Live-transcript monitoring during pilots.
- Daily transcript review in week one per client.
- Per-call analytics feeding the Monday report.

## 6. Functional requirements

The agent calls six backend tools (full JSON schemas in [RETELL_AGENT_CONFIG.md](RETELL_AGENT_CONFIG.md) §C):

| Tool | Purpose |
|---|---|
| `get_available_listings` | Search available units by beds / max_rent / pets / move-in date |
| `check_tour_slots` | Return available tour times for a property |
| `book_tour` | Book a confirmed slot (name, phone, consent) |
| `create_maintenance_ticket` | Log a routine maintenance issue |
| `escalate_emergency` | Alert on-call human by SMS + call for true emergencies |
| `take_message` | Record a message for anything outside the above |

Plus a **post-call webhook** (`/webhooks/retell`): store transcript → summarize → email the client → optional SMS to the prospect. Enforce the pilot minute cap here.

## 7. Non-functional requirements

- **Latency:** tool response < 800ms p95; agent begins speaking < 1.2s after the caller stops.
- **Multi-tenant from Day 1:** every table carries `client_id`; one agent config per client via dynamic variables.
- **Reliability:** no cold starts in production; graceful degradation when a tool is slow (agent says "one sec…").
- **Compact payloads:** every tool returns < 1KB JSON (tokens are latency).
- **Observability:** log every tool call with latency + payload; the QA gauntlet and Monday report run off these logs.

## 8. Compliance requirements (product-level, non-negotiable)

- **Fair Housing:** the agent never answers questions about who lives somewhere, demographics, "safe area," schools, or "what kind of people." Deflect with the exact scripted line. Treat every caller identically. Service/assistance-animal requests are accommodation requests — never refused.
- **TCPA:** SMS only after explicit verbal consent captured on the call (`sms_consent`). Never text without it.
- **Recording disclosure:** every call opens with "calls may be recorded for quality."
- **Honesty:** the agent always identifies itself as an AI when asked; never pretends to be human.

## 9. Success metrics & gates

| Gate | When | Pass condition |
|---|---|---|
| **A** | End of build | 9 / 10 consecutive adversarial gauntlet calls end correctly |
| **B** | ~Day 45 of outreach | 300 touches → ≥ 2 pilots live |
| **C** | ~Day 90 | ≥ 5 paying clients |

**North-star metric:** showings booked per client per week.

## 10. Constraints (real-world, shape the build)

- **Budget now: ~$0.** The entire product can be built and validated on free tiers + free credits + local dev. All paid tooling is deferred to the outreach phase. See [phases.md](phases.md) "Money timeline."
- **Founders in Pakistan (assumed):** US business hours (9–5 ET) = 6pm–2am PKT — the Closer's dial window and the agent's hardest shift. Some US-only tools (e.g. OpenPhone) have signup friction from Pakistan; see [rules.md](rules.md) §"Vendor/region notes" and [phases.md](phases.md) Phase 7.
- **Price:** $399/month flat, month-to-month; 14-day free pilot with a 300-minute hard cap; "5 showings in month one or you don't pay."
