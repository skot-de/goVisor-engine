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
do $$ begin
  if not exists (select 1 from pg_constraint
                  where conrelid = 'gov_lead_lots'::regclass and contype = 'p') then
    alter table gov_lead_lots add primary key (lead_id, lot_id);
  end if;
end $$;
-- RLS: Registrierung schaltet Leads frei; Analysen liegen hinter der Paywall
-- (die bekommen bewusst KEINE Policy und sind nur serverseitig lesbar).
alter table gov_lead_lots enable row level security;
drop policy if exists gov_lead_lots_read_authenticated on gov_lead_lots;
create policy gov_lead_lots_read_authenticated on gov_lead_lots
  for select to authenticated using (true);
