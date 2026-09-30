-- Mehrfachprofile & Seats — Phase 1 (additiv, verlustfrei). Konzept/Plan:
-- docs/mehrfachprofile-konzept.md, docs/mehrfachprofile-migrationsplan.md
--
-- WARUM. Heute ist es strikt 1:1 (user_profiles.id = auth.users.id → ein Login, ein
-- Suchprofil). Ein Unternehmen wie Canom soll mehrere Profile fuehren; Seats und Profile
-- sind kaufbar; ein Nutzer nutzt genau ein Profil aktiv (wechselbar).
--
-- ⚠ DIESE MIGRATION IST NUR DER ADDITIVE TEIL. Sie legt Tabellen/Spalten an und backfillt
-- den Bestand — sie aendert WEDER die merge_profile-RPC (0020) NOCH die Lesewege im Code.
-- Grund: schrieben wir schon jetzt in `profiles`, waehrend der Code weiter aus
-- `user_profiles.profile` liest, entstuende ein Fenster mit stillen Datenverlusten. Der
-- Umschlag auf das aktive Profil (RPC + auth.ts/profilBlob.ts + handle_new_user-Trigger)
-- ist Phase 2 und schlaegt mit dem Code ZUSAMMEN um. Bis dahin bleibt alles wie bisher
-- lauffaehig: jede Org hat nach dem Backfill genau ein Profil = der heutige Zustand.

-- ── organizations: das Unternehmen. Traeger von Abo, Seats und Profil-Kontingent ──────────
create table if not exists public.organizations (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,
  plan          text not null default 'free' check (plan in ('free','paid','cancelled')),
  plan_until    timestamptz,               -- wie user_profiles.plan_until (0015), auf Org-Ebene
  seats_paid    int  not null default 1 check (seats_paid    >= 1),  -- erlaubte Nutzer
  profiles_paid int  not null default 1 check (profiles_paid >= 1),  -- erlaubte Profile
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- ── profiles: die Suchprofile, der Org gehoerend ──────────────────────────────────────────
-- Die Felder spiegeln die heutigen Suchprofil-Spalten aus user_profiles (0001/0004). Sie
-- bleiben in Phase 1 auch dort bestehen (Dual-State); Phase 3 entfernt sie aus user_profiles.
create table if not exists public.profiles (
  id                 uuid primary key default gen_random_uuid(),
  org_id             uuid not null references public.organizations(id) on delete cascade,
  name               text not null default 'Standard',
  identity_id        text,
  confirmed_entities text[]  not null default '{}',
  cpv_fields         text[]  not null default '{}',
  cpv_labels         text[]  not null default '{}',
  regions            text[]  not null default '{}',
  region_labels      text[]  not null default '{}',
  vol_min            numeric,
  vol_max            numeric,
  branche            text,
  profile_type       text not null default 'bidder'
                     check (profile_type in ('bidder','contracting_authority')),
  profile            jsonb,                 -- der Engine-Blob, wie user_profiles.profile heute
  created_by         uuid references public.user_profiles(id) on delete set null,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);
create index if not exists profiles_org_idx on public.profiles (org_id);

-- ── user_profiles: bleibt Auth-Spiegel, bekommt Mitgliedschaft + aktives Profil ───────────
alter table public.user_profiles
  add column if not exists org_id            uuid references public.organizations(id) on delete cascade,
  add column if not exists active_profile_id uuid references public.profiles(id)      on delete set null,
  add column if not exists role              text not null default 'owner'
                                             check (role in ('owner','admin','member'));
create index if not exists user_profiles_org_idx on public.user_profiles (org_id);

-- ── RLS (Stil wie 0001) ───────────────────────────────────────────────────────────────────
alter table public.organizations enable row level security;
alter table public.profiles      enable row level security;

drop policy if exists "org_select_member" on public.organizations;
create policy "org_select_member" on public.organizations for select
  using (id = (select org_id from public.user_profiles where id = auth.uid()));

drop policy if exists "org_update_admin" on public.organizations;
create policy "org_update_admin" on public.organizations for update
  using (id = (select org_id from public.user_profiles where id = auth.uid())
         and (select role from public.user_profiles where id = auth.uid()) in ('owner','admin'));

drop policy if exists "profiles_select_member" on public.profiles;
create policy "profiles_select_member" on public.profiles for select
  using (org_id = (select org_id from public.user_profiles where id = auth.uid()));

-- owner/admin duerfen Profile ihrer Org anlegen/aendern/loeschen.
drop policy if exists "profiles_write_admin" on public.profiles;
create policy "profiles_write_admin" on public.profiles for all
  using (org_id = (select org_id from public.user_profiles where id = auth.uid())
         and (select role from public.user_profiles where id = auth.uid()) in ('owner','admin'))
  with check (org_id = (select org_id from public.user_profiles where id = auth.uid()));

-- updated_at pflegen (touch_updated_at stammt aus 0001)
drop trigger if exists organizations_touch on public.organizations;
create trigger organizations_touch before update on public.organizations
  for each row execute function public.touch_updated_at();
drop trigger if exists profiles_touch on public.profiles;
create trigger profiles_touch before update on public.profiles
  for each row execute function public.touch_updated_at();

-- ── Backfill: jeder bestehende Nutzer → eine Org + ein Profil + Owner-Mitgliedschaft ──────
-- Idempotent ueber `where org_id is null`: ein erneuter Lauf fasst schon migrierte Nutzer
-- nicht mehr an. Atomar in dieser Transaktion.
do $$
declare r record; v_org uuid; v_prof uuid;
begin
  for r in select * from public.user_profiles where org_id is null loop
    insert into public.organizations (name, plan, plan_until)
      values (coalesce(nullif(trim(r.company_name), ''), 'Mein Unternehmen'), r.plan, r.plan_until)
      returning id into v_org;
    insert into public.profiles (org_id, name, identity_id, confirmed_entities, cpv_fields,
                                 cpv_labels, regions, region_labels, vol_min, vol_max, branche,
                                 profile_type, profile, created_by)
      values (v_org, 'Standard', r.identity_id, r.confirmed_entities, r.cpv_fields,
              r.cpv_labels, r.regions, r.region_labels, r.vol_min, r.vol_max, r.branche,
              coalesce(r.profile_type, 'bidder'), r.profile, r.id)
      returning id into v_prof;
    update public.user_profiles
       set org_id = v_org, active_profile_id = v_prof, role = 'owner'
     where id = r.id;
  end loop;
end $$;

-- ── Selbstpruefung: nach dem Lauf traegt jeder Nutzer genau eine Org + ein aktives Profil ─
-- Bricht die Migration ab, wenn ein Nutzer ohne Org/aktives Profil bleibt oder ein Profil
-- verwaist ist. So ist ein halber Backfill unmoeglich.
do $$
declare n_ohne int; n_waisen int;
begin
  select count(*) into n_ohne from public.user_profiles
    where org_id is null or active_profile_id is null;
  select count(*) into n_waisen from public.profiles p
    left join public.organizations o on o.id = p.org_id where o.id is null;
  if n_ohne > 0 or n_waisen > 0 then
    raise exception 'Backfill unvollstaendig: % Nutzer ohne Org/Profil, % verwaiste Profile',
      n_ohne, n_waisen;
  end if;
end $$;

-- ── NOCH NICHT HIER (Phase 2, mit dem Code zusammen) ──────────────────────────────────────
-- · handle_new_user (0001) so erweitern, dass Selbst-Registrierung Org + erstes Profil +
--   role='owner' + active_profile_id anlegt (und Straggler re-backfillt, die zwischen 0024
--   und Phase 2 mit org_id=null entstanden sind).
-- · merge_profile (0020) auf das aktive Profil umstellen:
--       update public.profiles set profile = coalesce(profile,'{}') || p_patch
--        where id = (select active_profile_id from public.user_profiles where id = auth.uid());
-- · Grenzen durchsetzen: Trigger, der insert in profiles/user_profiles gegen
--   organizations.profiles_paid / seats_paid prueft (fail-closed).
