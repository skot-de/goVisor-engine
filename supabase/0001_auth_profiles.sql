-- goVisor Auth-Fundament (Ticket #6) — Muster übernommen aus mazh (public.users → auth.users, RLS).
-- Anwenden:  psql "$CONN" -f supabase/0001_auth_profiles.sql   (idempotent)

-- ── user_profiles: Spiegel von auth.users + das goVisor-Profil (Ticket #2/#7) ────────────
create table if not exists public.user_profiles (
  id                  uuid primary key references auth.users(id) on delete cascade,
  email               text not null,
  company_name        text,
  -- Identität (Ticket #7: Gruppe = Identität). entity_confidence ist das Billing-Gate (#6).
  identity_id         text,
  entity_confidence   text not null default 'none' check (entity_confidence in ('confirmed','probable','none')),
  confirmed_entities  text[] not null default '{}',
  -- Suchprofil (speist Relevanz-Engine)
  cpv_fields          text[] not null default '{}',
  cpv_labels          text[] not null default '{}',
  regions             text[] not null default '{}',
  region_labels       text[] not null default '{}',
  vol_min             numeric,
  vol_max             numeric,
  branche             text,                        -- Aspiring-Bidder-Pfad (ohne Firmenmatch)
  known_from_ted      boolean not null default false,
  -- Account-State (Ticket #6). Success-Fee/Billing kommt in eigener Migration.
  plan                text not null default 'free' check (plan in ('free','paid','cancelled')),
  grace_until         timestamptz,                 -- Erfolgsprämien-Schonfrist (6 Mo ab Upgrade)
  -- Vollständiges Engine-Profil als Blob (Flexibilität, ohne Schema-Migration bei Feldzuwachs)
  profile             jsonb,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  constraint user_profiles_email_not_empty check (length(trim(email)) > 0)
);

alter table public.user_profiles enable row level security;

-- Jeder sieht/ändert nur sein eigenes Profil (auth.uid() = id).
drop policy if exists "profiles_select_own" on public.user_profiles;
create policy "profiles_select_own" on public.user_profiles for select using (auth.uid() = id);

drop policy if exists "profiles_update_own" on public.user_profiles;
create policy "profiles_update_own" on public.user_profiles for update using (auth.uid() = id);

drop policy if exists "profiles_insert_own" on public.user_profiles;
create policy "profiles_insert_own" on public.user_profiles for insert with check (auth.uid() = id);

-- ── Automatisch ein Profil anlegen, sobald sich jemand registriert ───────────────────────
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.user_profiles (id, email)
  values (new.id, new.email)
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- updated_at pflegen
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end; $$;

drop trigger if exists user_profiles_touch on public.user_profiles;
create trigger user_profiles_touch before update on public.user_profiles
  for each row execute function public.touch_updated_at();
