-- Mehrfachprofile & Seats — Phase 2b: Invite-Flow. Baut auf 0024/0025 auf.
--
-- WARUM. Ein Unternehmen kauft Seats und laedt Kollegen ein. Ohne diesen Flow legt
-- `handle_new_user` (0025) fuer JEDE Registrierung eine Solo-Org an — ein Eingeladener
-- landete also in seiner eigenen Org statt in der des Unternehmens. Die Ausnahme dafuer war
-- in 0025 vorbereitet (ueberspringt, wenn die user_profiles-Zeile schon existiert); hier kommt
-- die eigentliche Zuordnung ueber die E-Mail dazu.

-- ── Offene Einladungen ────────────────────────────────────────────────────────────────────
create table if not exists public.pending_invites (
  id          uuid primary key default gen_random_uuid(),
  org_id      uuid not null references public.organizations(id) on delete cascade,
  email       text not null,
  role        text not null default 'member' check (role in ('admin','member')),
  invited_by  uuid references public.user_profiles(id) on delete set null,
  status      text not null default 'offen' check (status in ('offen','eingeloest','zurueckgezogen')),
  created_at  timestamptz not null default now()
);
-- Je Org und E-Mail hoechstens EINE offene Einladung.
create unique index if not exists pending_invites_offen_uk
  on public.pending_invites (org_id, lower(email)) where status = 'offen';
-- Schneller Zugriff beim Signup (ueber die E-Mail).
create index if not exists pending_invites_email_offen
  on public.pending_invites (lower(email)) where status = 'offen';

alter table public.pending_invites enable row level security;
-- Mitglieder sehen die Einladungen ihrer Org; owner/admin legen an / ziehen zurueck.
drop policy if exists "invites_select_member" on public.pending_invites;
create policy "invites_select_member" on public.pending_invites for select
  using (org_id = (select org_id from public.user_profiles where id = auth.uid()));
drop policy if exists "invites_write_admin" on public.pending_invites;
create policy "invites_write_admin" on public.pending_invites for all
  using (org_id = (select org_id from public.user_profiles where id = auth.uid())
         and (select role from public.user_profiles where id = auth.uid()) in ('owner','admin'))
  with check (org_id = (select org_id from public.user_profiles where id = auth.uid())
         and (select role from public.user_profiles where id = auth.uid()) in ('owner','admin'));

-- ── Seat-Grenze schon bei der EINLADUNG (fail-closed) ─────────────────────────────────────
-- Belegt zaehlen: bestehende Mitglieder + noch offene Einladungen. So kann man nie mehr
-- Sitze verplanen, als gekauft sind — die eigentliche user_profiles-Seat-Grenze (0025)
-- bleibt als zweiter Riegel beim Signup.
create or replace function public.pruefe_invite_seat()
returns trigger language plpgsql as $$
declare belegt int; grenze int;
begin
  select (select count(*) from public.user_profiles where org_id = new.org_id)
       + (select count(*) from public.pending_invites
            where org_id = new.org_id and status = 'offen')
    into belegt;
  select seats_paid into grenze from public.organizations where id = new.org_id;
  if grenze is not null and belegt >= grenze then
    raise exception 'Seat-Kontingent der Organisation erreicht (% Sitze belegt/eingeladen).', grenze
      using errcode = 'check_violation';
  end if;
  return new;
end;
$$;
drop trigger if exists pending_invites_seat on public.pending_invites;
create trigger pending_invites_seat before insert on public.pending_invites
  for each row when (new.status = 'offen')
  execute function public.pruefe_invite_seat();

-- ── handle_new_user: Eingeladene der Org zuordnen, sonst Solo-Org (ersetzt 0025) ──────────
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
declare v_org uuid; v_prof uuid; v_role text; v_invite uuid;
begin
  if exists (select 1 from public.user_profiles where id = new.id) then
    return new;                                   -- schon vorbereitet
  end if;

  -- Gibt es eine offene Einladung fuer diese E-Mail? Dann in DIE Org, kein Solo.
  select id, org_id, role into v_invite, v_org, v_role
    from public.pending_invites
   where status = 'offen' and lower(email) = lower(new.email)
   order by created_at limit 1;

  if v_invite is not null then
    -- aktives Profil = aeltestes Profil der Org (Mitglieder teilen die Org-Profile).
    select id into v_prof from public.profiles where org_id = v_org order by created_at limit 1;
    insert into public.user_profiles (id, email, org_id, active_profile_id, role)
      values (new.id, new.email, v_org, v_prof, v_role);
    update public.pending_invites set status = 'eingeloest' where id = v_invite;
  else
    insert into public.organizations (name) values ('Mein Unternehmen') returning id into v_org;
    insert into public.profiles (org_id, name) values (v_org, 'Standard') returning id into v_prof;
    insert into public.user_profiles (id, email, org_id, active_profile_id, role)
      values (new.id, new.email, v_org, v_prof, 'owner');
  end if;
  return new;
end;
$$;
