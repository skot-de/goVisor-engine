-- ── Gespeicherte Filter ──────────────────────────────────────────────────────
--
-- Eine gespeicherte Sicht ist MEHR ALS `Adv`. Wer „mein Filter" speichert, erwartet die
-- Liste zurueck, wie sie war: Grundraum (Branche), Schnellfilter, Suchtext, Suchtoken,
-- Sortierung. Wird nur der Filterzustand gesichert, kommt eine fremde Liste zurueck und
-- der Nutzer haelt das Speichern fuer kaputt.
--
-- ⚠ DIE FALLE IST DIE VERSIONIERUNG, nicht das Speichern. `Adv` waechst — allein heute
-- kamen Facettenzaehler dazu, und `user_lead_hidden` ist einen Tag alt. Ein Filter von
-- heute muss in sechs Monaten noch laden. Deshalb steht `fassung` in der Zeile, und beim
-- Lesen wird gegen `emptyAdv` gemischt: fehlende Schluessel bekommen ihren Vorgabewert,
-- unbekannte fliegen raus. Ohne das bricht es LAUTLOS — die Sicht sieht geladen aus und
-- filtert anders.
--
-- ⚠ `benachrichtigen` IST ABSICHTLICH TOT. Ein gespeicherter Filter ist der natuerliche
-- Traeger fuer „sag mir Bescheid, wenn etwas Neues passt" — `user_alert_settings` kann das
-- nicht, sie ist EINE Zeile je Nutzer und schaltet Arten, nicht Inhalte. Verdrahtet wird es
-- erst, wenn der Mailversand kein Platzhalter mehr ist (`web/lib/email.ts` meldet heute
-- Erfolg, ohne zu senden). Die Spalte steht hier, damit die Migration spaeter keine
-- Bestandsdaten anfassen muss.

create table if not exists public.user_filter (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references public.user_profiles(id) on delete cascade,
  name            text not null,
  fassung         int  not null default 1,
  zustand         jsonb not null,                       -- adv, filters, query, tokens, branche, sort
  benachrichtigen boolean not null default false,       -- ⚠ noch nicht verdrahtet, s. o.
  created_at      timestamptz not null default now(),
  zuletzt_genutzt timestamptz,
  unique (user_id, name)
);

alter table public.user_filter enable row level security;
drop policy if exists "filter_rw_own" on public.user_filter;
create policy "filter_rw_own" on public.user_filter
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

create index if not exists user_filter_user on public.user_filter (user_id, zuletzt_genutzt desc);
