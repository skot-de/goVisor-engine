-- gov_leads: generiert aus data/gold/DE/lead_export.parquet (nicht von Hand pflegen).
create table if not exists gov_leads (
  lead_id                  text not null,
  slug                     text unique,
  country                  text,
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
  contract_end_expected    date,
  cal_offset_days          integer,
  cal_spread_days          integer,
  days_to_expiry           bigint,
  procedure_kind           text,
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
  price_weight_pct         double precision,
  quality_weight_pct       double precision,
  cost_weight_pct          double precision,
  n_criteria               double precision,
  criteria_uniform         boolean,
  criteria_source          text,
  regulatory_regime        text,
  buyer_type               text,
  buyer_activity           text,
  documents_url            text,
  documents_source         text,
  has_documents            boolean,
  documents_paid           boolean,
  documents_languages      text,
  is_nationwide            boolean,
  guarantee_required       integer,
  variants_allowed         integer,
  validity_days            integer,
  selection_types          text,
  deadline_time            text,
  question_deadline        text,
  source_url               text,
  has_comparables          boolean,
  has_contract_history     boolean,
  updated_at               timestamptz default now(),
  primary key (lead_id)
);
-- Migration bestehender Tabellen (idempotent, neue Spalten nachziehen):
alter table gov_leads add column if not exists lead_id text;
alter table gov_leads add column if not exists slug text;
alter table gov_leads add column if not exists country text;
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
alter table gov_leads add column if not exists contract_end_expected date;
alter table gov_leads add column if not exists cal_offset_days integer;
alter table gov_leads add column if not exists cal_spread_days integer;
alter table gov_leads add column if not exists days_to_expiry bigint;
alter table gov_leads add column if not exists procedure_kind text;
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
alter table gov_leads add column if not exists price_weight_pct double precision;
alter table gov_leads add column if not exists quality_weight_pct double precision;
alter table gov_leads add column if not exists cost_weight_pct double precision;
alter table gov_leads add column if not exists n_criteria double precision;
alter table gov_leads add column if not exists criteria_uniform boolean;
alter table gov_leads add column if not exists criteria_source text;
alter table gov_leads add column if not exists regulatory_regime text;
alter table gov_leads add column if not exists buyer_type text;
alter table gov_leads add column if not exists buyer_activity text;
alter table gov_leads add column if not exists documents_url text;
alter table gov_leads add column if not exists documents_source text;
alter table gov_leads add column if not exists has_documents boolean;
alter table gov_leads add column if not exists documents_paid boolean;
alter table gov_leads add column if not exists documents_languages text;
alter table gov_leads add column if not exists is_nationwide boolean;
alter table gov_leads add column if not exists guarantee_required integer;
alter table gov_leads add column if not exists variants_allowed integer;
alter table gov_leads add column if not exists validity_days integer;
alter table gov_leads add column if not exists selection_types text;
alter table gov_leads add column if not exists deadline_time text;
alter table gov_leads add column if not exists question_deadline text;
alter table gov_leads add column if not exists source_url text;
alter table gov_leads add column if not exists has_comparables boolean;
alter table gov_leads add column if not exists has_contract_history boolean;
do $$ begin
  if not exists (select 1 from pg_constraint
                  where conrelid = 'gov_leads'::regclass and contype = 'p') then
    alter table gov_leads add primary key (lead_id);
  end if;
end $$;
create index if not exists gov_leads_phase_idx on gov_leads (phase);
create index if not exists gov_leads_market_nuts3_idx on gov_leads (market_nuts3);
create index if not exists gov_leads_buyer_nuts1_idx on gov_leads (buyer_nuts1);
create index if not exists gov_leads_contract_nature_idx on gov_leads (contract_nature);
create index if not exists gov_leads_value_band_idx on gov_leads (value_band);
create index if not exists gov_leads_deadline_date_idx on gov_leads (deadline_date);
create index if not exists gov_leads_incumbent_group_id_idx on gov_leads (incumbent_group_id);
create index if not exists gov_leads_has_detailed_description_idx on gov_leads (has_detailed_description);
drop index if exists gov_leads_slug_idx;   -- Dublette zu gov_leads_slug_key
-- RLS: Registrierung schaltet Leads frei; Analysen liegen hinter der Paywall
-- (die bekommen bewusst KEINE Policy und sind nur serverseitig lesbar).
alter table gov_leads enable row level security;
drop policy if exists gov_leads_read_authenticated on gov_leads;
create policy gov_leads_read_authenticated on gov_leads
  for select to authenticated using (true);
-- PostgREST cached das Schema. Eine NEU angelegte Tabelle ist ueber die REST-API
-- sonst nicht sichtbar (PGRST205: table not found in the schema cache),
-- obwohl sie in Postgres laengst existiert. Kostet nichts, wenn nichts neu ist.
notify pgrst, 'reload schema';


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
do $$ begin
  if not exists (select 1 from pg_constraint
                  where conrelid = 'gov_lead_cpv'::regclass and contype = 'p') then
    alter table gov_lead_cpv add primary key (lead_id, cpv_code);
  end if;
end $$;
drop index if exists gov_lead_cpv_slug_idx;   -- Dublette zu gov_lead_cpv_slug_key
-- RLS: Registrierung schaltet Leads frei; Analysen liegen hinter der Paywall
-- (die bekommen bewusst KEINE Policy und sind nur serverseitig lesbar).
alter table gov_lead_cpv enable row level security;
drop policy if exists gov_lead_cpv_read_authenticated on gov_lead_cpv;
create policy gov_lead_cpv_read_authenticated on gov_lead_cpv
  for select to authenticated using (true);
-- PostgREST cached das Schema. Eine NEU angelegte Tabelle ist ueber die REST-API
-- sonst nicht sichtbar (PGRST205: table not found in the schema cache),
-- obwohl sie in Postgres laengst existiert. Kostet nichts, wenn nichts neu ist.
notify pgrst, 'reload schema';


-- gov_lead_lots: generiert aus data/gold/DE/lead_lot.parquet (nicht von Hand pflegen).
create table if not exists gov_lead_lots (
  lead_id                  text not null,
  lot_cpv_code             text,
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
alter table gov_lead_lots add column if not exists lot_cpv_code text;
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
do $$ begin
  if not exists (select 1 from pg_constraint
                  where conrelid = 'gov_lead_lots'::regclass and contype = 'p') then
    alter table gov_lead_lots add primary key (lead_id, lot_id);
  end if;
end $$;
drop index if exists gov_lead_lots_slug_idx;   -- Dublette zu gov_lead_lots_slug_key
-- RLS: Registrierung schaltet Leads frei; Analysen liegen hinter der Paywall
-- (die bekommen bewusst KEINE Policy und sind nur serverseitig lesbar).
alter table gov_lead_lots enable row level security;
drop policy if exists gov_lead_lots_read_authenticated on gov_lead_lots;
create policy gov_lead_lots_read_authenticated on gov_lead_lots
  for select to authenticated using (true);
-- PostgREST cached das Schema. Eine NEU angelegte Tabelle ist ueber die REST-API
-- sonst nicht sichtbar (PGRST205: table not found in the schema cache),
-- obwohl sie in Postgres laengst existiert. Kostet nichts, wenn nichts neu ist.
notify pgrst, 'reload schema';


-- gov_lead_criteria: generiert aus data/gold/DE/lead_criteria.parquet (nicht von Hand pflegen).
create table if not exists gov_lead_criteria (
  lead_id                  text not null,
  lot_id                   text not null,
  criterion_no             bigint not null,
  criterion_kind           text,
  criterion_name           text,
  weight_kind              text,
  weight_pct               double precision,
  weight_raw               double precision,
  is_rank                  boolean,
  weight_usable            boolean,
  updated_at               timestamptz default now(),
  primary key (lead_id, lot_id, criterion_no)
);
-- Migration bestehender Tabellen (idempotent, neue Spalten nachziehen):
alter table gov_lead_criteria add column if not exists lead_id text;
alter table gov_lead_criteria add column if not exists lot_id text;
alter table gov_lead_criteria add column if not exists criterion_no bigint;
alter table gov_lead_criteria add column if not exists criterion_kind text;
alter table gov_lead_criteria add column if not exists criterion_name text;
alter table gov_lead_criteria add column if not exists weight_kind text;
alter table gov_lead_criteria add column if not exists weight_pct double precision;
alter table gov_lead_criteria add column if not exists weight_raw double precision;
alter table gov_lead_criteria add column if not exists is_rank boolean;
alter table gov_lead_criteria add column if not exists weight_usable boolean;
do $$ begin
  if not exists (select 1 from pg_constraint
                  where conrelid = 'gov_lead_criteria'::regclass and contype = 'p') then
    alter table gov_lead_criteria add primary key (lead_id, lot_id, criterion_no);
  end if;
end $$;
drop index if exists gov_lead_criteria_slug_idx;   -- Dublette zu gov_lead_criteria_slug_key
-- RLS: Registrierung schaltet Leads frei; Analysen liegen hinter der Paywall
-- (die bekommen bewusst KEINE Policy und sind nur serverseitig lesbar).
alter table gov_lead_criteria enable row level security;
drop policy if exists gov_lead_criteria_read_authenticated on gov_lead_criteria;
create policy gov_lead_criteria_read_authenticated on gov_lead_criteria
  for select to authenticated using (true);
-- PostgREST cached das Schema. Eine NEU angelegte Tabelle ist ueber die REST-API
-- sonst nicht sichtbar (PGRST205: table not found in the schema cache),
-- obwohl sie in Postgres laengst existiert. Kostet nichts, wenn nichts neu ist.
notify pgrst, 'reload schema';


-- gov_lead_requirements: generiert aus data/gold/DE/lead_requirement.parquet (nicht von Hand pflegen).
create table if not exists gov_lead_requirements (
  lead_id                  text not null,
  lot_id                   text not null,
  requirement_no           bigint not null,
  requirement_kind         text,
  requirement_code         text,
  requirement_text         text,
  requirement_length       bigint,
  updated_at               timestamptz default now(),
  primary key (lead_id, lot_id, requirement_no)
);
-- Migration bestehender Tabellen (idempotent, neue Spalten nachziehen):
alter table gov_lead_requirements add column if not exists lead_id text;
alter table gov_lead_requirements add column if not exists lot_id text;
alter table gov_lead_requirements add column if not exists requirement_no bigint;
alter table gov_lead_requirements add column if not exists requirement_kind text;
alter table gov_lead_requirements add column if not exists requirement_code text;
alter table gov_lead_requirements add column if not exists requirement_text text;
alter table gov_lead_requirements add column if not exists requirement_length bigint;
do $$ begin
  if not exists (select 1 from pg_constraint
                  where conrelid = 'gov_lead_requirements'::regclass and contype = 'p') then
    alter table gov_lead_requirements add primary key (lead_id, lot_id, requirement_no);
  end if;
end $$;
drop index if exists gov_lead_requirements_slug_idx;   -- Dublette zu gov_lead_requirements_slug_key
-- RLS: Registrierung schaltet Leads frei; Analysen liegen hinter der Paywall
-- (die bekommen bewusst KEINE Policy und sind nur serverseitig lesbar).
alter table gov_lead_requirements enable row level security;
drop policy if exists gov_lead_requirements_read_authenticated on gov_lead_requirements;
create policy gov_lead_requirements_read_authenticated on gov_lead_requirements
  for select to authenticated using (true);
-- PostgREST cached das Schema. Eine NEU angelegte Tabelle ist ueber die REST-API
-- sonst nicht sichtbar (PGRST205: table not found in the schema cache),
-- obwohl sie in Postgres laengst existiert. Kostet nichts, wenn nichts neu ist.
notify pgrst, 'reload schema';


-- gov_lead_parties: generiert aus data/gold/DE/lead_party.parquet (nicht von Hand pflegen).
create table if not exists gov_lead_parties (
  lead_id                  text not null,
  party_role               text not null,
  party_no                 smallint not null,
  party_name               text,
  national_id              text,
  town                     text,
  postal_code              text,
  country                  text,
  nuts                     text,
  email                    text,
  phone                    text,
  contact_person           text,
  url                      text,
  is_sme                   boolean,
  in_consortium            boolean,
  updated_at               timestamptz default now(),
  primary key (lead_id, party_role, party_no)
);
-- Migration bestehender Tabellen (idempotent, neue Spalten nachziehen):
alter table gov_lead_parties add column if not exists lead_id text;
alter table gov_lead_parties add column if not exists party_role text;
alter table gov_lead_parties add column if not exists party_no smallint;
alter table gov_lead_parties add column if not exists party_name text;
alter table gov_lead_parties add column if not exists national_id text;
alter table gov_lead_parties add column if not exists town text;
alter table gov_lead_parties add column if not exists postal_code text;
alter table gov_lead_parties add column if not exists country text;
alter table gov_lead_parties add column if not exists nuts text;
alter table gov_lead_parties add column if not exists email text;
alter table gov_lead_parties add column if not exists phone text;
alter table gov_lead_parties add column if not exists contact_person text;
alter table gov_lead_parties add column if not exists url text;
alter table gov_lead_parties add column if not exists is_sme boolean;
alter table gov_lead_parties add column if not exists in_consortium boolean;
do $$ begin
  if not exists (select 1 from pg_constraint
                  where conrelid = 'gov_lead_parties'::regclass and contype = 'p') then
    alter table gov_lead_parties add primary key (lead_id, party_role, party_no);
  end if;
end $$;
drop index if exists gov_lead_parties_slug_idx;   -- Dublette zu gov_lead_parties_slug_key
-- RLS: Registrierung schaltet Leads frei; Analysen liegen hinter der Paywall
-- (die bekommen bewusst KEINE Policy und sind nur serverseitig lesbar).
alter table gov_lead_parties enable row level security;
drop policy if exists gov_lead_parties_read_authenticated on gov_lead_parties;
create policy gov_lead_parties_read_authenticated on gov_lead_parties
  for select to authenticated using (true);
-- PostgREST cached das Schema. Eine NEU angelegte Tabelle ist ueber die REST-API
-- sonst nicht sichtbar (PGRST205: table not found in the schema cache),
-- obwohl sie in Postgres laengst existiert. Kostet nichts, wenn nichts neu ist.
notify pgrst, 'reload schema';


-- gov_bronze_inventory: generiert aus data/gold/DE/bronze_inventory.parquet (nicht von Hand pflegen).
create table if not exists gov_bronze_inventory (
  schema_gen               text not null,
  path                     text not null,
  n_values                 bigint,
  n_notices                bigint,
  coverage_pct             double precision,
  max_length               bigint,
  example_value            text,
  is_attribute             boolean,
  derived_column           text,
  is_used                  boolean,
  updated_at               timestamptz default now(),
  primary key (schema_gen, path)
);
-- Migration bestehender Tabellen (idempotent, neue Spalten nachziehen):
alter table gov_bronze_inventory add column if not exists schema_gen text;
alter table gov_bronze_inventory add column if not exists path text;
alter table gov_bronze_inventory add column if not exists n_values bigint;
alter table gov_bronze_inventory add column if not exists n_notices bigint;
alter table gov_bronze_inventory add column if not exists coverage_pct double precision;
alter table gov_bronze_inventory add column if not exists max_length bigint;
alter table gov_bronze_inventory add column if not exists example_value text;
alter table gov_bronze_inventory add column if not exists is_attribute boolean;
alter table gov_bronze_inventory add column if not exists derived_column text;
alter table gov_bronze_inventory add column if not exists is_used boolean;
do $$ begin
  if not exists (select 1 from pg_constraint
                  where conrelid = 'gov_bronze_inventory'::regclass and contype = 'p') then
    alter table gov_bronze_inventory add primary key (schema_gen, path);
  end if;
end $$;
drop index if exists gov_bronze_inventory_slug_idx;   -- Dublette zu gov_bronze_inventory_slug_key
-- RLS: Registrierung schaltet Leads frei; Analysen liegen hinter der Paywall
-- (die bekommen bewusst KEINE Policy und sind nur serverseitig lesbar).
alter table gov_bronze_inventory enable row level security;
drop policy if exists gov_bronze_inventory_read_authenticated on gov_bronze_inventory;
create policy gov_bronze_inventory_read_authenticated on gov_bronze_inventory
  for select to authenticated using (true);
-- PostgREST cached das Schema. Eine NEU angelegte Tabelle ist ueber die REST-API
-- sonst nicht sichtbar (PGRST205: table not found in the schema cache),
-- obwohl sie in Postgres laengst existiert. Kostet nichts, wenn nichts neu ist.
notify pgrst, 'reload schema';
