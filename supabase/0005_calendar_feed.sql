-- goVisor — Verfahrenskalender iCal-Abo (Ticket #16 §8.2).
-- Ein nicht-erratbarer Feed-Token je Nutzer; der Feed liest LIVE aus user_watchlist
-- (keine Duplikation der Termine). Paid-Feature — Gate im API-Route, nicht in der DDL.
-- Anwenden:  psql "$CONN" -f supabase/0005_calendar_feed.sql   (idempotent)

create table if not exists public.user_calendar_feed (
  user_id     uuid primary key references auth.users(id) on delete cascade,
  feed_token  text not null unique default encode(gen_random_bytes(18), 'hex'),
  created_at  timestamptz not null default now()
);

alter table public.user_calendar_feed enable row level security;

-- Nur der Eigentümer verwaltet seinen Feed-Token (Anlegen/Ansehen/Neu-Generieren).
-- Der Feed-Endpoint selbst liest server-seitig über den Token (Service-Role), nicht via RLS.
drop policy if exists "calfeed_select_own" on public.user_calendar_feed;
create policy "calfeed_select_own" on public.user_calendar_feed for select using (auth.uid() = user_id);

drop policy if exists "calfeed_insert_own" on public.user_calendar_feed;
create policy "calfeed_insert_own" on public.user_calendar_feed for insert with check (auth.uid() = user_id);

drop policy if exists "calfeed_delete_own" on public.user_calendar_feed;
create policy "calfeed_delete_own" on public.user_calendar_feed for delete using (auth.uid() = user_id);

comment on table public.user_calendar_feed is
  'iCal-Feed-Token je Nutzer (Ticket #16). Der .ics-Endpoint löst token→user_id→user_watchlist '
  'auf und emittiert die Angebotsfristen der beobachteten Leads. Token neu generierbar (delete+insert).';
