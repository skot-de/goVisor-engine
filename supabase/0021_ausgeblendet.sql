-- ── Ausgeblendete Vorgaenge ──────────────────────────────────────────────────
--
-- Neben „merken" braucht die Trefferliste das Gegenteil: wegklicken. Der Wettbewerber
-- auftraege.io hat dafuer ein durchgestrichenes Auge neben dem Stern, und der Knopf ist
-- mehr als Kosmetik: jedes Ausblenden ist ein NEGATIVES BEISPIEL fuer die Passung, und es
-- kostet den Nutzer einen Klick statt eines Formulars.
--
-- ⚠ EIGENE TABELLE, NICHT `user_lead_interactions`. Die misst Klicks (Attribution, erster
-- Detailaufruf). Ausblenden ist eine ABSICHT. Wer beides in eine Tabelle legt, kann spaeter
-- nicht mehr sagen, ob eine Zeile „angesehen" oder „abgelehnt" bedeutet.
--
-- ⚠ TITEL UND KAEUFER GEHEN MIT, aus demselben Grund wie bei `user_watchlist` (0017):
-- `export_web_leads.py` wirft Vorgaenge mit abgelaufener Frist aus dem Frontend-Export.
-- Ohne Kontext waere eine ausgeblendete Zeile spaeter nicht mehr deutbar — und genau die
-- Ablehnungen sind das Material, aus dem die Passung lernen soll.
--
-- `grund` bleibt absichtlich OPTIONAL und ohne Auswahlliste. Der Wert des Knopfes ist, dass
-- er einen Klick kostet; wer eine Pflichtbegruendung davorsetzt, bekommt keine Daten.

create table if not exists public.user_lead_hidden (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references public.user_profiles(id) on delete cascade,
  lead_id     text not null,
  titel       text,
  buyer_name  text,
  grund       text,                                    -- optional, keine Auswahlliste
  created_at  timestamptz not null default now(),
  unique (user_id, lead_id)
);

alter table public.user_lead_hidden enable row level security;
drop policy if exists "hidden_rw_own" on public.user_lead_hidden;
create policy "hidden_rw_own" on public.user_lead_hidden
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

create index if not exists user_lead_hidden_user on public.user_lead_hidden (user_id);
