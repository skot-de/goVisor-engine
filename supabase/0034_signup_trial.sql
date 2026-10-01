-- Preismodell v1.9 §3a — Testphase: jede Selbst-Registrierung startet mit 4 Wochen Vollzugang.
--
-- WARUM. Die AUSWERTUNG der Testphase steht schon (web/lib/stufeZuTier.js: tier='trial' +
-- trial_ends_at in der Zukunft → 'pro', sonst 'free'; fehlendes Datum = abgelaufen). Was fehlte,
-- ist der SETZ-Teil: `handle_new_user` legte eine Solo-Org bisher auf dem Default tier='free'
-- an (gemessen: 0 von 13 Orgs tragen ein trial_ends_at). Diese Migration setzt beim
-- Solo-Registrierungs-Zweig tier='trial' + trial_ends_at = now()+28 Tage.
--
-- ⚠ NUR DER SOLO-ZWEIG. Ein Eingeladener tritt einer BESTEHENDEN Org bei und erbt deren Stufe
-- (sonst setzte eine Einladung die ganze Org auf Trial zurueck). Der Invite-Zweig bleibt wortgleich.
-- ⚠ Basiert auf der LIVE-Definition (0026) — nur die eine organizations-insert-Zeile aendert sich.
-- `tier`/`trial_ends_at` existieren seit 0028 (eingespielt). Der Abfall auf Free passiert ohne
-- weiteren Setz-Schritt, rein ueber die Auswertung (stufeZuTier) nach Ablauf.

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
declare v_org uuid; v_prof uuid; v_role text; v_invite uuid;
begin
  if exists (select 1 from public.user_profiles where id = new.id) then
    return new;                                   -- schon vorbereitet
  end if;

  -- Gibt es eine offene Einladung fuer diese E-Mail? Dann in DIE Org, kein Solo, keine Testphase.
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
    -- §3a: neue Selbst-Registrierung → vier Wochen Vollzugang (Testphase).
    insert into public.organizations (name, tier, trial_ends_at)
      values ('Mein Unternehmen', 'trial', now() + interval '28 days') returning id into v_org;
    insert into public.profiles (org_id, name) values (v_org, 'Standard') returning id into v_prof;
    insert into public.user_profiles (id, email, org_id, active_profile_id, role)
      values (new.id, new.email, v_org, v_prof, 'owner');
  end if;
  return new;
end;
$$;
