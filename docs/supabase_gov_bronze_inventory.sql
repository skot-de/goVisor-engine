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
