-- PropTalk US - demo seed: Willowbrook Property Management (Tampa) + 8 listings.
-- Fixed UUIDs + ON CONFLICT DO NOTHING => safe to re-run.
-- Variety by design: 1-3 beds, $1350-$2400, pets yes/no, availability spread,
-- and one 'leased' unit (2C) that must NEVER appear in search (honesty test).

insert into clients (id, company_name, agent_name, timezone, escalation_phone, notify_email, plan, minutes_cap)
values ('11111111-1111-1111-1111-111111111111', 'Willowbrook Property Management', 'Maya', 'America/New_York', '+18135550100', 'owner@willowbrookpm.com', 'pilot', 300)
on conflict (id) do nothing;

insert into properties (id, client_id, code, label, address, beds, baths, sqft, rent, deposit, available_date, pets_allowed, pet_policy, parking, highlights, status) values
('22222222-0000-0000-0000-000000000001','11111111-1111-1111-1111-111111111111','2A','Unit 2A - Willowbrook Apartments','4210 Bayshore Ave, Tampa, FL',2,2,980,1795,1795,current_date + 7,true,'Dogs under 40lb and cats, 300 dollar pet deposit','1 assigned spot','Renovated kitchen and a screened balcony','available'),
('22222222-0000-0000-0000-000000000002','11111111-1111-1111-1111-111111111111','5C','Unit 5C - Willowbrook Apartments','4210 Bayshore Ave, Tampa, FL',1,1,640,1350,1350,current_date,false,'No pets','Street parking','Top floor with tons of natural light','available'),
('22222222-0000-0000-0000-000000000003','11111111-1111-1111-1111-111111111111','PALM','Palm Grove House','118 Palm Grove Dr, Tampa, FL',3,2,1450,2350,2350,current_date + 30,true,'All pets welcome, 400 dollar deposit','2-car garage','Fenced yard and brand-new AC','available'),
('22222222-0000-0000-0000-000000000004','11111111-1111-1111-1111-111111111111','1B','Unit 1B - Willowbrook Apartments','4210 Bayshore Ave, Tampa, FL',1,1,700,1425,1425,current_date + 14,true,'Cats only, 200 dollar deposit','1 assigned spot','Ground floor with a private patio','available'),
('22222222-0000-0000-0000-000000000005','11111111-1111-1111-1111-111111111111','3D','Unit 3D - Willowbrook Apartments','4210 Bayshore Ave, Tampa, FL',2,1,900,1650,1650,current_date,false,'No pets','Street parking','Walk to Bayshore with an updated bathroom','available'),
('22222222-0000-0000-0000-000000000006','11111111-1111-1111-1111-111111111111','BAY','Bayshore Bungalow','512 Bayshore Ave, Tampa, FL',2,2,1100,2100,2100,current_date + 45,true,'Dogs and cats welcome, 350 dollar deposit','Driveway parking for two','Cozy bungalow with a large kitchen','available'),
('22222222-0000-0000-0000-000000000007','11111111-1111-1111-1111-111111111111','4B','Unit 4B - Willowbrook Apartments','4210 Bayshore Ave, Tampa, FL',3,2,1250,2400,2400,current_date + 30,false,'No pets','1 assigned spot plus guest parking','Corner unit with extra storage','available'),
('22222222-0000-0000-0000-000000000008','11111111-1111-1111-1111-111111111111','2C','Unit 2C - Willowbrook Apartments','4210 Bayshore Ave, Tampa, FL',2,2,980,1750,1750,current_date - 10,true,'Dogs under 40lb and cats, 300 dollar pet deposit','1 assigned spot','Just leased, identical layout to 2A','leased')
on conflict (id) do update set code = excluded.code;
