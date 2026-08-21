-- Feature #11 „Treffergüte" — Nutzer-Tabellen (§8.1/§8.3/§8.4). Muster wie 0003_user_contracts.
-- Idempotent. Anwenden: psql "$CONN" -f supabase/0007_trefferguete.sql
--
-- WICHTIG (§8.3 / AC12): user_outcomes hat KEINE Verbindung zu irgendeiner Abrechnung —
-- kein Fremdschlüssel, keine gemeinsame View. Die Erfolgsprämie, gegen die diese Regel
-- ursprünglich schützte, ist am 2026-08-21 gestrichen (s. 0012). Die Regel bleibt, weil sie
-- für jedes künftige Preismodell gilt: Melden darf nie teurer sein als Schweigen.

-- ── §8.1 user_declarations: alle erklärten Angaben, einheitlich ──
create table if not exists public.user_declarations (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references public.user_profiles(id) on delete cascade,
  kind          text not null,        -- capability|certificate|guarantee|volume_limit|region|exclusion|regulatory|partnership|prequalification|reference|capacity
  key           text not null,        -- z. B. data_engineering, iso_27001
  value         jsonb,                -- typabhängig (Band, Betrag, Datum, Boolean)
  source        text,                 -- onboarding|requirement_check|trefferguete|dismiss_reason
  declared_at   timestamptz not null default now(),
  confirmed_at  timestamptz,
  valid_until   date,
  unique (user_id, kind, key)
);
create index if not exists user_declarations_user_idx on public.user_declarations(user_id);

alter table public.user_declarations enable row level security;
drop policy if exists "declarations_rw_own" on public.user_declarations;
create policy "declarations_rw_own" on public.user_declarations
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ── §8.3 user_outcomes: Ergebnismeldungen (Moat) — bewusst KEIN FK zu einer Abrechnung ──
create table if not exists public.user_outcomes (
  id                   uuid primary key default gen_random_uuid(),
  user_id              uuid not null references public.user_profiles(id) on delete cascade,
  lead_id              text not null,
  applied              boolean not null default false,
  dismiss_reason       text,          -- bei applied=false
  result               text check (result in ('won','lost','cancelled','excluded')),
  rank                 int,           -- Rangplatz laut Absage
  loss_reason          text check (loss_reason in ('price','quality','formal','reference','unknown')),
  reported_at          timestamptz not null default now(),
  usable_for_aggregate boolean not null default false,
  -- denormalisierter Kontext für die private Bilanz (kein Aggregat-Rückfluss, kein Join nötig):
  titel                text,
  buyer_name           text,
  value_euro           numeric,
  updated_at           timestamptz not null default now(),
  unique (user_id, lead_id)
);
create index if not exists user_outcomes_user_idx on public.user_outcomes(user_id);

alter table public.user_outcomes enable row level security;
drop policy if exists "outcomes_rw_own" on public.user_outcomes;
create policy "outcomes_rw_own" on public.user_outcomes
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop trigger if exists user_outcomes_touch on public.user_outcomes;
create trigger user_outcomes_touch before update on public.user_outcomes
  for each row execute function public.touch_updated_at();

-- ── §8.4 user_gap_effects: vorberechnete Wirkung je Lücke (nächtlich/on-demand) ──
create table if not exists public.user_gap_effects (
  user_id        uuid not null references public.user_profiles(id) on delete cascade,
  gap_key        text not null,
  affected_leads int not null default 0,
  computed_at    timestamptz not null default now(),
  primary key (user_id, gap_key)
);

alter table public.user_gap_effects enable row level security;
drop policy if exists "gap_effects_rw_own" on public.user_gap_effects;
create policy "gap_effects_rw_own" on public.user_gap_effects
  using (auth.uid() = user_id) with check (auth.uid() = user_id);
