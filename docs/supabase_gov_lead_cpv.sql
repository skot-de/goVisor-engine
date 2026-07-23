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
-- RLS: Registrierung schaltet Leads frei; Analysen liegen hinter der Paywall
-- (die bekommen bewusst KEINE Policy und sind nur serverseitig lesbar).
alter table gov_lead_cpv enable row level security;
drop policy if exists gov_lead_cpv_read_authenticated on gov_lead_cpv;
create policy gov_lead_cpv_read_authenticated on gov_lead_cpv
  for select to authenticated using (true);
