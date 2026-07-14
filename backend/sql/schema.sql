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
  property_id uuid references properties(id),
  prospect_name text,
  prospect_phone text,
  slot_start timestamptz,
  cal_booking_id text,
  sms_consent bool default false,   -- captured verbally on-call (TCPA)
  status text default 'booked',     -- booked | rescheduled | no_show | toured
  created_at timestamptz default now()
);

create table if not exists maintenance_tickets (
  id uuid primary key default gen_random_uuid(),
  client_id uuid,
  call_id uuid,
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
  caller_name text,
  callback_number text,
  reason text,
  body text,
  created_at timestamptz default now()
);
