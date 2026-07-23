-- gov_leads: generiert aus data/gold/DE/lead_export.parquet (nicht von Hand pflegen).
create table if not exists gov_leads (
  lead_id                  text primary key,
  slug                     text unique,
  title                    text,
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
  updated_at               timestamptz default now()
);
create index if not exists gov_leads_slug_idx on gov_leads (slug);
create index if not exists gov_leads_phase_idx on gov_leads (phase);
create index if not exists gov_leads_market_nuts3_idx on gov_leads (market_nuts3);
create index if not exists gov_leads_buyer_nuts1_idx on gov_leads (buyer_nuts1);
create index if not exists gov_leads_contract_nature_idx on gov_leads (contract_nature);
create index if not exists gov_leads_value_band_idx on gov_leads (value_band);
create index if not exists gov_leads_deadline_date_idx on gov_leads (deadline_date);
create index if not exists gov_leads_incumbent_group_id_idx on gov_leads (incumbent_group_id);
-- RLS: Registrierung schaltet Leads frei; Analysen liegen hinter der Paywall
-- (die bekommen bewusst KEINE Policy und sind nur serverseitig lesbar).
alter table gov_leads enable row level security;
drop policy if exists gov_leads_read_authenticated on gov_leads;
create policy gov_leads_read_authenticated on gov_leads
  for select to authenticated using (true);
