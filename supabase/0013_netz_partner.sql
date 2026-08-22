-- goVisor: Partnersuche für Mehr-Los-Vergaben (Feature I) — der fehlende Unterbau
-- Anwenden:  Supabase Dashboard → SQL Editor   (DDL läuft in diesem Projekt nur dort)
--
-- WARUM ES DAS BRAUCHT. Die Oberfläche stand seit Monaten: „Interesse bekunden",
-- „Kontakt freigeben", „Eine Firma ergänzt euch". Dahinter lag nichts. `netzPartner`
-- schrieb NIEMAND (0 von 43.199 Leads), und die Interessensmeldung war ein `Set` im
-- Browserspeicher: weg beim Neuladen, für niemanden sonst sichtbar. Ein Treffer konnte
-- nicht entstehen, auch nicht theoretisch.
--
-- ⚠ DATENSCHUTZ IST HIER DIE HAUPTSACHE. Wer sich für welche Ausschreibung meldet, ist
-- Wettbewerbsinformation ersten Ranges. Deshalb:
--   · RLS erlaubt jedem NUR die eigenen Zeilen. Fremde Meldungen sind über die
--     Client-Verbindung nicht lesbar, auch nicht gezählt.
--   · Das Matching läuft serverseitig mit dem Secret-Key (lib/supabase/admin.ts) und gibt
--     nur zurück, was der Fragende sehen darf: Feld, Größenklasse, gedeckte Lose. Der NAME
--     der Gegenseite erst, wenn BEIDE freigegeben haben.
--   · Wer sich selbst nicht gemeldet hat, bekommt gar nichts zu sehen. Keine Zählung,
--     kein „hier interessiert sich jemand".

create table if not exists public.netz_interesse (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references public.user_profiles(id) on delete cascade,
  -- Die bestätigte Firmengruppe. Ohne sie kein Match: zwei Konten derselben Firma dürfen
  -- sich nicht gegenseitig als Partner vorgeschlagen bekommen.
  identity_id  text,
  lead_id      text not null,
  -- Losnummern, die die Firma SELBST abdecken kann. Das ist die eigentliche Angabe:
  -- ohne sie gibt es keine Ergänzung, sondern nur zwei Firmen auf demselben Los.
  lose         int[] not null default '{}',
  -- Kontaktfreigabe, einseitig setzbar, wirksam nur beidseitig.
  freigabe     boolean not null default false,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  unique (user_id, lead_id)
);

create index if not exists netz_interesse_lead on public.netz_interesse (lead_id);

alter table public.netz_interesse enable row level security;

drop policy if exists "netz_rw_own" on public.netz_interesse;
create policy "netz_rw_own" on public.netz_interesse
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop trigger if exists netz_touch on public.netz_interesse;
create trigger netz_touch before update on public.netz_interesse
  for each row execute function public.touch_updated_at();
