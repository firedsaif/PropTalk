-- PropTalk US - database schema (Supabase / Postgres).
-- Safe to re-run: uses IF NOT EXISTS. Row-Level Security is added before
-- onboarding real clients (see docs/rules.md), not in this dev seed.

create table if not exists clients (
  id uuid primary key default gen_random_uuid(),
  company_name text not null,
  agent_name text default 'Maya',
  timezone text default 'America/New_York',
  escalation_phone text,            -- on-call human for emergencies
  notify_email text,                -- receives post-call summaries
  cal_event_type_id text,           -- Cal.com event type for tours
  plan text default 'pilot',        -- pilot | active | churned
  minutes_cap int default 300,      -- pilot hard cap
  minutes_used int default 0,
  created_at timestamptz default now()
);

create table if not exists properties (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references clients(id),
  code text,                        -- short, speakable id the agent uses: '2A', 'PALM'
  label text not null,              -- 'Unit 4B - Willowbrook Apartments'
  address text,
  beds int,
  baths numeric,
  sqft int,
  rent int,
  deposit int,
  available_date date,
  pets_allowed bool default false,
  pet_policy text,
  parking text,
  highlights text,                  -- one-liner the agent can say naturally
  status text default 'available',  -- available | leased | off_market
  created_at timestamptz default now()
);
create index if not exists idx_properties_search on properties (client_id, status, beds, rent);
-- The table may predate the `code` column (Phase 1) - add it explicitly for re-runs.
alter table properties add column if not exists code text;
-- The agent passes this short code back into check_tour_slots and book_tour (unique per client).
create unique index if not exists idx_properties_code
  on properties (client_id, lower(code)) where code is not null;

create table if not exists calls (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references clients(id),
  retell_call_id text unique,
  from_number text,
  started_at timestamptz,
  ended_at timestamptz,
  duration_sec int,
  intent text,                      -- leasing | tour | maintenance | message | other
  outcome text,                     -- tour_booked | ticket_created | escalated | message_taken | info_only
  summary text,
  transcript text,
  recording_url text
);

create table if not exists tour_bookings (
  id uuid primary key default gen_random_uuid(),
  client_id uuid,
  call_id uuid references calls(id),
  retell_call_id text,              -- set at booking time, before the calls row exists
  property_id uuid references properties(id),
  prospect_name text,
  prospect_phone text,
  slot_start timestamptz,
  cal_booking_id text,              -- Cal.com booking uid (Phase 4); null = calendar write degraded
  sms_consent bool default false,   -- captured verbally on-call (TCPA)
  status text default 'booked',     -- booked | rescheduled | cancelled | no_show | toured
  created_at timestamptz default now()
);
-- The table may already exist from Phase 1 - CREATE TABLE IF NOT EXISTS above is then a no-op,
-- so add the Phase 2 column explicitly for re-runs against an existing database.
alter table tour_bookings add column if not exists retell_call_id text;
-- Idempotency: a retried book_tour call for the same call+property+slot must not create a duplicate.
-- Scoped to status='booked' (Phase 4): once a slot is released by a reschedule/cancel it must be
-- re-bookable, including by the call that originally held it ("actually, make it 10am after all").
-- Dropped first so a database created before Phase 4 picks up the narrower predicate.
drop index if exists idx_tour_bookings_idempotency;
create unique index if not exists idx_tour_bookings_idempotency
  on tour_bookings (retell_call_id, property_id, slot_start)
  where retell_call_id is not null and status = 'booked';
-- Conflict guard: never let two active bookings hold the same property+slot.
create unique index if not exists idx_tour_bookings_slot_taken
  on tour_bookings (property_id, slot_start)
  where status = 'booked';

create table if not exists maintenance_tickets (
  id uuid primary key default gen_random_uuid(),
  client_id uuid,
  call_id uuid,
  retell_call_id text,              -- set at tool time, before the calls row exists
  unit text,
  issue_type text,
  severity text check (severity in ('routine','urgent','emergency')),
  description text,
  callback_number text,
  permission_to_enter bool,
  status text default 'open',
  created_at timestamptz default now()
);

create table if not exists messages (
  id uuid primary key default gen_random_uuid(),
  client_id uuid,
  call_id uuid,
  retell_call_id text,              -- set at tool time, before the calls row exists
  caller_name text,
  callback_number text,
  reason text,
  body text,
  created_at timestamptz default now()
);

-- Phase 4: the post-call summary email reports what happened on *this* call, so every
-- outcome table needs to be findable by retell_call_id (tour_bookings already was).
-- Added explicitly for re-runs against a database created before Phase 4.
alter table maintenance_tickets add column if not exists retell_call_id text;
alter table messages add column if not exists retell_call_id text;
create index if not exists idx_maintenance_tickets_call on maintenance_tickets (retell_call_id);
create index if not exists idx_messages_call on messages (retell_call_id);
create index if not exists idx_tour_bookings_call on tour_bookings (retell_call_id);
