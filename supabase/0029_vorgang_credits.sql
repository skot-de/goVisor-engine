-- Preismodell v1.9 §4.3 — Vorgangs-Kontingent (Free: 3 Vorgaenge/Monat). Baut auf 0024 auf.
--
-- LEITREGEL (v1.9 §1): Was pro Ausschreibung passiert, ist unbegrenzt; was ueber
-- Ausschreibungen hinweg geht, staffelt. Das Free-Kontingent ist die eine Zahl, die das
-- umsetzt: drei VORGAENGE im Monat. Ein Vorgang ist (§4.3) ENTWEDER ein Lead mit allem
-- daran (Bewertung, Unterlagen, Empfehlung + die Firmenprofile der beteiligten Firmen),
-- ODER ein einzeln aufgerufenes Firmenprofil. Der Ausloeser ist das erste Oeffnen von
-- Unterlagen ODER Bewertung je Lead — danach bleibt der Vorgang DAUERHAFT offen, auch ueber
-- den Monatswechsel. Firmenprofile im Lead-Kontext zaehlen NICHT mit.
--
-- ⚠ DREI ENTWURFSENTSCHEIDUNGEN, bewusst:
-- 1) EINE Tabelle statt zweier (§13 nennt `vorgang_credits` + `unlocked_leads`): die
--    Monats-Zahl wird aus den Freischalt-Zeitstempeln ABGELEITET, nicht separat gezaehlt.
--    Ein zweiter Zaehler koennte driften; die Freigabe selbst ist die Wahrheit.
-- 2) `art` ∈ {lead, firma}: Lead-Aufschluss und einzeln aufgerufenes Firmenprofil sind
--    beide ein Vorgang (§4.3, "eine Zahl, eine Einheit"). Firmenprofile IM Lead-Kontext
--    ruft die App gar nicht hier auf — sie zaehlen deshalb nie.
-- 3) Das LIMIT ist SERVER-AUTORITATIV und NICHT client-manipulierbar: Freischalten geht nur
--    ueber die `security definer`-RPC (wie `kauf_gutschreiben`, 0027), die die App mit dem
--    serverseitig aus der Stufe berechneten Limit ruft. Kein Insert-Recht fuer Clients.
--
-- Entkoppelt von 0028 (tier): die RPC nimmt das Limit als Parameter; die App leitet es aus
-- `getTier()` ab (Paywall aus → unbegrenzt, wie heute). 0029 haengt NICHT an 0028.

create table if not exists public.vorgang_freigaben (
  id                 uuid primary key default gen_random_uuid(),
  org_id             uuid not null references public.organizations(id) on delete cascade,
  art                text not null check (art in ('lead','firma')),
  ref                text not null,                     -- lead_id bzw. identity_id
  freigeschaltet_am  timestamptz not null default now(),
  durch              uuid references public.user_profiles(id) on delete set null,
  unique (org_id, art, ref)                             -- ein Vorgang je Org nur einmal
);
create index if not exists vorgang_freigaben_org_monat
  on public.vorgang_freigaben (org_id, freigeschaltet_am);

alter table public.vorgang_freigaben enable row level security;
-- Mitglieder sehen die Freigaben ihrer Org (fuer Zaehler + Historie). Geschrieben wird NUR
-- serverseitig ueber die RPC — kein Insert/Update/Delete-Policy fuer Clients, sonst waere das
-- Monatslimit client-seitig umgehbar.
drop policy if exists "vorgang_select_member" on public.vorgang_freigaben;
create policy "vorgang_select_member" on public.vorgang_freigaben for select
  using (org_id = (select org_id from public.user_profiles where id = auth.uid()));

-- Idempotente, limit-pruefende Freischaltung. Rueckgabe:
--   'schon_frei'      — Vorgang war schon offen (kein Verbrauch, bleibt dauerhaft)
--   'limit_erreicht'  — Free-Monatslimit voll, NICHT freigeschaltet
--   'freigeschaltet'  — neu freigeschaltet (zaehlt auf den Monat)
-- p_limit NULL = unbegrenzt (bezahlte Stufen bzw. Paywall aus). Das Limit kommt vom Server
-- (lib/vorgang.ts), nie vom Client — die Funktion ist service-definer und client-gesperrt.
create or replace function public.vorgang_freischalten(
  p_org uuid, p_art text, p_ref text, p_limit int default null, p_durch uuid default null
) returns text language plpgsql security definer set search_path = public as $$
declare v_count int;
begin
  if p_art not in ('lead','firma') then raise exception 'ungueltige art: %', p_art; end if;
  if p_ref is null or length(p_ref) = 0 or length(p_ref) > 200 then raise exception 'ungueltige ref'; end if;
  perform 1 from public.vorgang_freigaben where org_id = p_org and art = p_art and ref = p_ref;
  if found then return 'schon_frei'; end if;                 -- dauerhaft offen (§4.3)
  if p_limit is not null then
    select count(*) into v_count from public.vorgang_freigaben
      where org_id = p_org
        and date_trunc('month', freigeschaltet_am) = date_trunc('month', now());
    if v_count >= p_limit then return 'limit_erreicht'; end if;
  end if;
  insert into public.vorgang_freigaben (org_id, art, ref, durch)
    values (p_org, p_art, p_ref, p_durch)
    on conflict (org_id, art, ref) do nothing;
  return 'freigeschaltet';
end;
$$;
-- ⚠ NUR service_role. Supabase gewaehrt neuen public-Funktionen per Default EXECUTE an anon
-- UND authenticated; `revoke from public` allein entfernt diese EINZEL-Grants NICHT. Ohne den
-- Entzug koennte ein (sogar nicht angemeldeter) Client die RPC mit beliebigem p_limit direkt
-- rufen und das Kontingent umgehen. Die App ruft ausschliesslich ueber den Service-Key.
revoke all on function public.vorgang_freischalten(uuid,text,text,int,uuid) from public, anon, authenticated;
