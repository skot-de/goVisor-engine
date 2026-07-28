-- Eigener Vertragsbestand (Ticket #11 §8.2) — speist die Strategie-Sektion „Bindung" (#10 §5.7):
-- eigene auslaufende Verträge, gebundene Kapazität, Konzentrationsrisiko, Re-Tender-Vorschau.
-- Ein gewonnener (Rahmen-)Vertrag bindet beim Auslaufen wieder Kapazität → Verteidigungssignal.
-- Idempotent. Anwenden: psql "$CONN" -f supabase/0003_user_contracts.sql

create table if not exists public.user_contracts (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references public.user_profiles(id) on delete cascade,
  lead_id       text,                                   -- Herkunfts-Lead, falls aus goVisor markiert
  buyer_name    text,
  buyer_entity_id text,                                 -- Match gegen den Entity-Graph (optional)
  titel         text,
  cpv_bundle    text,
  nuts_code     text,
  value_euro    numeric,
  is_framework  boolean not null default false,         -- Rahmenvertrag (bindet Abrufkapazität)
  start_date    date,
  end_date      date,
  source        text not null default 'declared' check (source in ('declared','matched_ted','won_in_app')),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index if not exists user_contracts_user_idx on public.user_contracts(user_id);
create index if not exists user_contracts_end_idx on public.user_contracts(user_id, end_date);

alter table public.user_contracts enable row level security;
drop policy if exists "contracts_rw_own" on public.user_contracts;
create policy "contracts_rw_own" on public.user_contracts
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop trigger if exists user_contracts_touch on public.user_contracts;
create trigger user_contracts_touch before update on public.user_contracts
  for each row execute function public.touch_updated_at();
