-- Identitäts-Ansprüche: wer behauptet, zu welcher Firma zu gehören — und wie gut das belegt ist.
--
-- Hintergrund: Bis hierher stand im Onboarding hart `entityConfidence: "confirmed"`. Mit einer
-- Freemail-Adresse konnte jeder eine beliebige Firma für sich beanspruchen. Gemessen an den
-- Vergabedaten betrifft der Fall 5,8 % unserer Zielgruppe (1.061 von 18.388 Firmen mit ≥3
-- Zuschlägen) — selten genug für eine manuelle Prüfung, häufig genug, um sie zu brauchen.
-- Die Hälfte davon sind t-online-Adressen: etablierte Mittelständler, keine Betrugsversuche.

create table if not exists public.identity_claims (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references public.user_profiles(id) on delete cascade,
  identity_id   text not null,          -- grp:/solo: aus entity_identity
  company_name  text not null,          -- Anzeigename zum Zeitpunkt des Anspruchs
  email_domain  text,                   -- Domain der Registrierungs-Adresse (nicht die Adresse)
  -- 'belegt'      = Domain stimmt mit der aus den Vergabedaten bekannten überein
  -- 'unbestaetigt'= Freemail oder abweichende Domain, noch ungeprüft
  -- 'geprueft'    = manuell bestätigt
  -- 'abgelehnt'   = manuell zurückgewiesen
  status        text not null default 'unbestaetigt'
                check (status in ('belegt', 'unbestaetigt', 'geprueft', 'abgelehnt')),
  grund         text,                   -- maschinelle Begründung (für den Nutzer sichtbar)
  nachricht     text,                   -- was der Nutzer selbst zur Prüfung schreibt
  bearbeitet_am timestamptz,
  bearbeitet_von text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create index if not exists identity_claims_offen_idx
  on public.identity_claims (created_at desc) where status = 'unbestaetigt';
create index if not exists identity_claims_user_idx on public.identity_claims (user_id);

alter table public.identity_claims enable row level security;

-- Der Nutzer sieht und stellt nur eigene Anträge. Die Entscheidung (status/bearbeitet_*)
-- trifft ausschließlich der Service-Key — sonst könnte man sich selbst freischalten.
drop policy if exists "claims_rw_own" on public.identity_claims;
create policy "claims_rw_own" on public.identity_claims
  for select using (auth.uid() = user_id);

drop policy if exists "claims_insert_own" on public.identity_claims;
create policy "claims_insert_own" on public.identity_claims
  for insert with check (auth.uid() = user_id);

drop trigger if exists identity_claims_touch on public.identity_claims;
create trigger identity_claims_touch before update on public.identity_claims
  for each row execute function public.touch_updated_at();
