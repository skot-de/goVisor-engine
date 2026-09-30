-- Mehrfachprofile & Seats — Phase 2 (DB-Seite). Baut auf 0024 auf.
-- Schlaegt ZUSAMMEN mit dem Frontend-Code um (auth.ts loadProfile/saveProfile, useProfil,
-- /api/profil/wechseln). Alles hier ist TOLERANT: solange ein Nutzer kein active_profile_id
-- hat (vor 0024 oder als Straggler), verhaelt sich alles wie bisher gegen user_profiles.

-- 0) Straggler nachziehen — Nutzer, die zwischen 0024 und 0025 ohne Org entstanden sind.
-- Idempotent (where org_id is null); identisch zum 0024-Backfill.
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
    update public.user_profiles set org_id = v_org, active_profile_id = v_prof, role = 'owner'
     where id = r.id;
  end loop;
end $$;

-- 1) merge_profile schreibt ins AKTIVE Profil (sonst user_profiles). Ersetzt 0020.
-- security invoker: RLS auf profiles (0024) stellt sicher, dass nur ein eigenes Org-Profil
-- getroffen wird; die active_profile_id gehoert ohnehin dem Aufrufer.
create or replace function public.merge_profile(p_patch jsonb)
returns void language plpgsql security invoker set search_path = public as $$
declare v_prof uuid;
begin
  if p_patch is null or jsonb_typeof(p_patch) <> 'object' then
    raise exception 'merge_profile: p_patch muss ein JSON-Objekt sein';
  end if;
  select active_profile_id into v_prof from public.user_profiles where id = auth.uid();
  if v_prof is not null then
    update public.profiles
       set profile = coalesce(profile, '{}'::jsonb) || p_patch
     where id = v_prof;
  else
    update public.user_profiles
       set profile = coalesce(profile, '{}'::jsonb) || p_patch
     where id = auth.uid();
  end if;
end;
$$;
revoke all on function public.merge_profile(jsonb) from public;
grant execute on function public.merge_profile(jsonb) to authenticated;

-- 2) Selbst-Registrierung legt Org + erstes Profil + Owner an (erweitert 0001).
-- ⚠ Eingeladene Nutzer (Invite-Flow, spaeter) duerfen hier KEINE neue Org bekommen — der
-- Invite-Pfad setzt org_id/role selbst und ueberspringt diesen Trigger-Zweig (dann waere
-- die Einladung schon als user_profiles-Zeile vorbereitet; erst DANN legt Supabase auth an).
-- Bis es den Invite-Flow gibt, ist jede Registrierung eine Solo-Org.
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
declare v_org uuid; v_prof uuid; v_exists boolean;
begin
  select true into v_exists from public.user_profiles where id = new.id;
  if v_exists then return new; end if;   -- schon vorbereitet (Invite) → nichts tun
  insert into public.organizations (name) values ('Mein Unternehmen') returning id into v_org;
  insert into public.profiles (org_id, name) values (v_org, 'Standard') returning id into v_prof;
  insert into public.user_profiles (id, email, org_id, active_profile_id, role)
    values (new.id, new.email, v_org, v_prof, 'owner')
    on conflict (id) do nothing;
  return new;
end;
$$;

-- 3) Grenzen durchsetzen (fail-closed, zusaetzlich zur App-Meldung).
create or replace function public.pruefe_profil_grenze()
returns trigger language plpgsql as $$
declare n int; grenze int;
begin
  select count(*) into n from public.profiles where org_id = new.org_id;
  select profiles_paid into grenze from public.organizations where id = new.org_id;
  if grenze is not null and n >= grenze then
    raise exception 'Profil-Kontingent der Organisation erreicht (% Profile).', grenze
      using errcode = 'check_violation';
  end if;
  return new;
end;
$$;
drop trigger if exists profiles_grenze on public.profiles;
create trigger profiles_grenze before insert on public.profiles
  for each row execute function public.pruefe_profil_grenze();

create or replace function public.pruefe_seat_grenze()
returns trigger language plpgsql as $$
declare n int; grenze int;
begin
  select count(*) into n from public.user_profiles where org_id = new.org_id;
  select seats_paid into grenze from public.organizations where id = new.org_id;
  if grenze is not null and n >= grenze then
    raise exception 'Seat-Kontingent der Organisation erreicht (% Nutzer).', grenze
      using errcode = 'check_violation';
  end if;
  return new;
end;
$$;
drop trigger if exists user_profiles_seat_grenze on public.user_profiles;
create trigger user_profiles_seat_grenze before insert on public.user_profiles
  for each row when (new.org_id is not null)
  execute function public.pruefe_seat_grenze();
