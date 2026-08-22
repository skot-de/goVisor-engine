-- goVisor: Posteingang für Hinweise (Ticket #9, in-app statt E-Mail)
-- Anwenden:  Supabase Dashboard → SQL Editor
--
-- WARUM. Die Alarm-Logik (`lib/alerts.ts`) und die Schalter in den Einstellungen stehen seit
-- Monaten. Zugestellt wurde nie etwas: `lib/email.ts` ist ein Stub ohne Provider, und einen
-- Posteingang gab es nicht. Die Startseite versprach trotzdem „Meldung, sobald etwas
-- Passendes erscheint".
--
-- ⚠ SCHLIMMER ALS NICHTS: der Cron-Lauf (`/api/alerts/run`) setzt nach dem Stub-Versand die
-- `*_sent`-Flags in `user_watchlist`. Der Hinweis gilt damit als zugestellt, obwohl ihn
-- niemand bekommen hat, und `dueAlerts` liefert ihn nie wieder. Jeder Lauf hätte also
-- Hinweise VERBRAUCHT statt sie auszuliefern.
--
-- Deshalb bekommt der Posteingang eigene Zeilen und rührt die `*_sent`-Flags nicht an:
-- die bleiben die Buchhaltung des E-Mail-Wegs, diese Tabelle ist die Zustellung.

create table if not exists public.user_alerts (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references public.user_profiles(id) on delete cascade,
  lead_id    text not null,
  typ        text not null check (typ in ('deadline_14d','deadline_3d','expiry_90d','expiry_30d')),
  titel      text not null default '',
  tage       int,
  created_at timestamptz not null default now(),
  gesehen_am timestamptz,
  -- Ein Hinweis je Lead und Art. Das ist die Entdopplung: der Posteingang darf beim
  -- zweiten Aufruf am selben Tag nicht dieselbe Meldung erneut anlegen.
  unique (user_id, lead_id, typ)
);

create index if not exists user_alerts_offen
  on public.user_alerts (user_id, gesehen_am, created_at desc);

alter table public.user_alerts enable row level security;

drop policy if exists "alerts_rw_own" on public.user_alerts;
create policy "alerts_rw_own" on public.user_alerts
  using (auth.uid() = user_id) with check (auth.uid() = user_id);
