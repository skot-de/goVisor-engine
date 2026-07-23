-- gov_leads: generiert aus data/gold/DE/lead_export.parquet (nicht von Hand pflegen).
create table if not exists gov_leads (
  lead_id                  text not null,
  slug                     text unique,
  title                    text,
  description              text,
  description_length       bigint,
  total_description_length double precision,
  has_detailed_description boolean,
  n_lots                   bigint,
  buyer_name               text,
  buyer_town               text,
  buyer_nuts               text,
  buyer_nuts1              text,
  buyer_region_name        text,
  market_nuts3             text,
  market_region_name       text,
  market_region_known      boolean,
  cpv_code                 text,
  contract_kind            text,
  phase                    text,
  is_new_tender            boolean,
  contract_nature          text,
  contract_nature_source   text,
  value_eur                double precision,
  value_band               text,
  value_source             text,
  deadline_date            date,
  days_to_deadline         bigint,
  months_to_expiry         bigint,
  contract_end             date,
  days_to_expiry           bigint,
  due_basis                text,
  timing_implausible       boolean,
  timing_source            text,
  incumbent_name           text,
  incumbent_since_year     integer,
  incumbent_confidence     double precision,
  incumbent_source         text,
  incumbent_group_id       text,
  incumbent_group_size     bigint,
  switch_chance            text,
  n_bidders                integer,
  single_bidder            boolean,
  competition_level        text,
  competition_source       text,
  source_url               text,
  has_comparables          boolean,
  has_contract_history     boolean,
  updated_at               timestamptz default now(),
  primary key (lead_id)
);
-- Migration bestehender Tabellen (idempotent, neue Spalten nachziehen):
alter table gov_leads add column if not exists lead_id text;
alter table gov_leads add column if not exists slug text;
alter table gov_leads add column if not exists title text;
alter table gov_leads add column if not exists description text;
alter table gov_leads add column if not exists description_length bigint;
alter table gov_leads add column if not exists total_description_length double precision;
alter table gov_leads add column if not exists has_detailed_description boolean;
alter table gov_leads add column if not exists n_lots bigint;
alter table gov_leads add column if not exists buyer_name text;
alter table gov_leads add column if not exists buyer_town text;
alter table gov_leads add column if not exists buyer_nuts text;
alter table gov_leads add column if not exists buyer_nuts1 text;
alter table gov_leads add column if not exists buyer_region_name text;
alter table gov_leads add column if not exists market_nuts3 text;
alter table gov_leads add column if not exists market_region_name text;
alter table gov_leads add column if not exists market_region_known boolean;
alter table gov_leads add column if not exists cpv_code text;
alter table gov_leads add column if not exists contract_kind text;
alter table gov_leads add column if not exists phase text;
alter table gov_leads add column if not exists is_new_tender boolean;
alter table gov_leads add column if not exists contract_nature text;
alter table gov_leads add column if not exists contract_nature_source text;
alter table gov_leads add column if not exists value_eur double precision;
alter table gov_leads add column if not exists value_band text;
alter table gov_leads add column if not exists value_source text;
alter table gov_leads add column if not exists deadline_date date;
alter table gov_leads add column if not exists days_to_deadline bigint;
alter table gov_leads add column if not exists months_to_expiry bigint;
alter table gov_leads add column if not exists contract_end date;
alter table gov_leads add column if not exists days_to_expiry bigint;
alter table gov_leads add column if not exists due_basis text;
alter table gov_leads add column if not exists timing_implausible boolean;
alter table gov_leads add column if not exists timing_source text;
alter table gov_leads add column if not exists incumbent_name text;
alter table gov_leads add column if not exists incumbent_since_year integer;
alter table gov_leads add column if not exists incumbent_confidence double precision;
alter table gov_leads add column if not exists incumbent_source text;
alter table gov_leads add column if not exists incumbent_group_id text;
alter table gov_leads add column if not exists incumbent_group_size bigint;
alter table gov_leads add column if not exists switch_chance text;
alter table gov_leads add column if not exists n_bidders integer;
alter table gov_leads add column if not exists single_bidder boolean;
alter table gov_leads add column if not exists competition_level text;
alter table gov_leads add column if not exists competition_source text;
alter table gov_leads add column if not exists source_url text;
alter table gov_leads add column if not exists has_comparables boolean;
alter table gov_leads add column if not exists has_contract_history boolean;
create index if not exists gov_leads_slug_idx on gov_leads (slug);
create index if not exists gov_leads_phase_idx on gov_leads (phase);
create index if not exists gov_leads_market_nuts3_idx on gov_leads (market_nuts3);
create index if not exists gov_leads_buyer_nuts1_idx on gov_leads (buyer_nuts1);
create index if not exists gov_leads_contract_nature_idx on gov_leads (contract_nature);
create index if not exists gov_leads_value_band_idx on gov_leads (value_band);
create index if not exists gov_leads_deadline_date_idx on gov_leads (deadline_date);
create index if not exists gov_leads_incumbent_group_id_idx on gov_leads (incumbent_group_id);
create index if not exists gov_leads_has_detailed_description_idx on gov_leads (has_detailed_description);
-- RLS: Registrierung schaltet Leads frei; Analysen liegen hinter der Paywall
-- (die bekommen bewusst KEINE Policy und sind nur serverseitig lesbar).
alter table gov_leads enable row level security;
drop policy if exists gov_leads_read_authenticated on gov_leads;
create policy gov_leads_read_authenticated on gov_leads
  for select to authenticated using (true);


-- gov_lead_cpv: generiert aus data/gold/DE/lead_cpv.parquet (nicht von Hand pflegen).
create table if not exists gov_lead_cpv (
  lead_id                  text not null,
  cpv_code                 text not null,
  is_main                  boolean,
  updated_at               timestamptz default now(),
  primary key (lead_id, cpv_code)
);
-- Migration bestehender Tabellen (idempotent, neue Spalten nachziehen):
alter table gov_lead_cpv add column if not exists lead_id text;
alter table gov_lead_cpv add column if not exists cpv_code text;
alter table gov_lead_cpv add column if not exists is_main boolean;
-- RLS: Registrierung schaltet Leads frei; Analysen liegen hinter der Paywall
-- (die bekommen bewusst KEINE Policy und sind nur serverseitig lesbar).
alter table gov_lead_cpv enable row level security;
drop policy if exists gov_lead_cpv_read_authenticated on gov_lead_cpv;
create policy gov_lead_cpv_read_authenticated on gov_lead_cpv
  for select to authenticated using (true);


-- gov_lead_lots: generiert aus data/gold/DE/lead_lot.parquet (nicht von Hand pflegen).
create table if not exists gov_lead_lots (
  lead_id                  text not null,
  lot_id                   text not null,
  lot_id_synthetic         boolean,
  lot_title                text,
  lot_description          text,
  lot_description_length   bigint,
  lot_value_eur            double precision,
  lot_value_currency       text,
  start_date               date,
  end_date                 date,
  duration_months          integer,
  lot_market_nuts3         text,
  has_options              boolean,
  options_description      text,
  has_renewal              boolean,
  renewal_description      text,
  max_renewals             integer,
  updated_at               timestamptz default now(),
  primary key (lead_id, lot_id)
);
-- Migration bestehender Tabellen (idempotent, neue Spalten nachziehen):
alter table gov_lead_lots add column if not exists lead_id text;
alter table gov_lead_lots add column if not exists lot_id text;
alter table gov_lead_lots add column if not exists lot_id_synthetic boolean;
alter table gov_lead_lots add column if not exists lot_title text;
alter table gov_lead_lots add column if not exists lot_description text;
alter table gov_lead_lots add column if not exists lot_description_length bigint;
alter table gov_lead_lots add column if not exists lot_value_eur double precision;
alter table gov_lead_lots add column if not exists lot_value_currency text;
alter table gov_lead_lots add column if not exists start_date date;
alter table gov_lead_lots add column if not exists end_date date;
alter table gov_lead_lots add column if not exists duration_months integer;
alter table gov_lead_lots add column if not exists lot_market_nuts3 text;
alter table gov_lead_lots add column if not exists has_options boolean;
alter table gov_lead_lots add column if not exists options_description text;
alter table gov_lead_lots add column if not exists has_renewal boolean;
alter table gov_lead_lots add column if not exists renewal_description text;
alter table gov_lead_lots add column if not exists max_renewals integer;
-- RLS: Registrierung schaltet Leads frei; Analysen liegen hinter der Paywall
-- (die bekommen bewusst KEINE Policy und sind nur serverseitig lesbar).
alter table gov_lead_lots enable row level security;
drop policy if exists gov_lead_lots_read_authenticated on gov_lead_lots;
create policy gov_lead_lots_read_authenticated on gov_lead_lots
  for select to authenticated using (true);
