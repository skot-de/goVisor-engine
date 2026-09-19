-- ── Lead-Status, dauerhaft ───────────────────────────────────────────────────
--
-- Der Status (interessant / pruefung / fragen / verworfen) war bis zum 2026-09-19 reiner
-- Speicher-Zustand: `setWf` setzte `l.userStatus` am Objekt, `logEvent` schrieb in ein
-- Feld, das niemand sichert. Ein Neuladen loeschte die Einordnung einer ganzen Sitzung.
--
-- ⚠ AUFGEFALLEN IST ES AM NACHBARN. In derselben Zeile steht der Stern, und der
-- persistiert seit 0017 korrekt nach `user_watchlist`. Zwei Klicks nebeneinander, einer
-- ueberlebt das Neuladen und einer nicht — das merkt man erst, wenn man danach sucht.
--
-- ⚠ EIGENE TABELLE, NICHT `user_lead_hidden` oder `user_watchlist`. Die drei sind
-- verschiedene Aussagen: merken heisst „behalte das im Blick", ausblenden heisst „weg
-- damit", der Status heisst „so weit bin ich damit". Wer sie zusammenlegt, kann spaeter
-- nicht mehr sagen, was eine Zeile bedeutet hat. Dieselbe Begruendung steht in 0021.
--
-- ⚠ TITEL UND KAEUFER GEHEN MIT, wie in 0017 und 0021 begruendet: `export_web_leads.py`
-- wirft Vorgaenge mit abgelaufener Frist aus dem Frontend-Export. Ein Vorgang, den jemand
-- als „In Pruefung" markiert hat, verschwaende sonst am Tag nach der Frist spurlos — und
-- gerade der ist die wertvollste Nachfrage, die wir stellen koennen („habt ihr
-- mitgeboten?").
--
-- ⚠ EIN STATUS JE VORGANG, also `unique (user_id, lead_id)` und ein UPSERT, der den Wert
-- WIRKLICH UEBERSCHREIBT. Watchlist und Hidden fahren `ignoreDuplicates` — dort ist die
-- blosse Existenz der Zeile die Aussage. Hier ist es der Wert; mit `ignoreDuplicates`
-- wuerde jede ZWEITE Statusaenderung lautlos verpuffen, und zwar nur die zweite, was den
-- Fehler beim Testen fast unsichtbar macht.

create table if not exists public.user_lead_status (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references public.user_profiles(id) on delete cascade,
  lead_id     text not null,
  status      text not null check (status in ('interessant','pruefung','fragen','verworfen')),
  titel       text,
  buyer_name  text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (user_id, lead_id)
);

alter table public.user_lead_status enable row level security;
drop policy if exists "lead_status_rw_own" on public.user_lead_status;
create policy "lead_status_rw_own" on public.user_lead_status
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

create index if not exists user_lead_status_user on public.user_lead_status (user_id);
