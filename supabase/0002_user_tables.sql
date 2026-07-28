-- goVisor User-Tabellen (Tickets #6 Billing, #8 Analytics, #9 Alerts, #10 Settings).
-- Alle mit RLS: Nutzer sieht nur eigene Zeilen. Schreibende Billing-Vorgänge laufen
-- serverseitig über den Secret-Key (umgeht RLS) — dafür keine insert/update-Policy.
-- Idempotent. Anwenden: psql "$CONN" -f supabase/0002_user_tables.sql

-- ── Alert-Einstellungen (Ticket #9/#10 §4) ───────────────────────────────────
create table if not exists public.user_alert_settings (
  user_id                  uuid primary key references public.user_profiles(id) on delete cascade,
  deadline_warning_enabled boolean not null default true,   -- „Angebotsfrist naht" (primär)
  expiry_warning_enabled   boolean not null default false,  -- „Vertrag läuft aus" (nur echte Enden)
  award_notify_enabled     boolean not null default true,   -- „Zuschlag erteilt"
  new_leads_digest_enabled boolean not null default false,  -- Neue-Leads-Digest (Marketing → Opt-in)
  frequency                text not null default 'daily' check (frequency in ('instant','daily','weekly')),
  timezone                 text not null default 'Europe/Berlin',
  updated_at               timestamptz not null default now()
);
alter table public.user_alert_settings enable row level security;
drop policy if exists "alerts_rw_own" on public.user_alert_settings;
create policy "alerts_rw_own" on public.user_alert_settings using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ── Watchlist + Alert-Zustand je Lead (Ticket #9) ────────────────────────────
create table if not exists public.user_watchlist (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references public.user_profiles(id) on delete cascade,
  lead_id          text not null,
  auto             boolean not null default false,          -- auto-gematcht vs. manuell gemerkt
  deadline_14d_sent boolean not null default false,
  deadline_3d_sent boolean not null default false,
  expiry_warn_sent boolean not null default false,
  created_at       timestamptz not null default now(),
  unique (user_id, lead_id)
);
alter table public.user_watchlist enable row level security;
drop policy if exists "watch_rw_own" on public.user_watchlist;
create policy "watch_rw_own" on public.user_watchlist using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ── Lead-Interaktionen (Attribution für Success-Fee #6 + Analytics #8) ────────
create table if not exists public.user_lead_interactions (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid not null references public.user_profiles(id) on delete cascade,
  lead_id           text not null,
  first_click_at    timestamptz not null default now(),     -- erster Detail-Klick (Attribution)
  first_analysis_at timestamptz,                             -- erster Bewertungs-Tab-Klick
  unique (user_id, lead_id)
);
alter table public.user_lead_interactions enable row level security;
drop policy if exists "inter_rw_own" on public.user_lead_interactions;
create policy "inter_rw_own" on public.user_lead_interactions using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ── Success-Fee-Rechnungen (Ticket #6, HITL-Modell) ──────────────────────────
-- KEIN FK zu einer Fee-Kalkulation (Ticket #11 §8.3-Prinzip). Schreiben nur serverseitig.
create table if not exists public.success_fee_charges (
  id                        uuid primary key default gen_random_uuid(),
  user_id                   uuid not null references public.user_profiles(id) on delete cascade,
  lead_id                   text,
  tender_publication_number text,
  award_date                date,
  value_source              text check (value_source in ('echt','kunde_bestaetigt','kunde_offen')),
  award_value_band          text,
  anchor_band               text,
  fee_amount                numeric,
  status                    text not null default 'draft'
                              check (status in ('draft','needs_confirmation','disputed','sent','paid','waived','failed')),
  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now()
);
alter table public.success_fee_charges enable row level security;
-- Nur LESEN der eigenen Rechnungen; angelegt/geändert wird serverseitig (Secret-Key umgeht RLS).
drop policy if exists "fees_select_own" on public.success_fee_charges;
create policy "fees_select_own" on public.success_fee_charges for select using (auth.uid() = user_id);

-- ── GDPR-Datenexport-Anforderung (Ticket #10 §5, Art. 20) ────────────────────
create table if not exists public.user_data_export (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references public.user_profiles(id) on delete cascade,
  requested_at timestamptz not null default now(),
  status       text not null default 'pending' check (status in ('pending','ready','failed')),
  download_url text
);
alter table public.user_data_export enable row level security;
drop policy if exists "export_rw_own" on public.user_data_export;
create policy "export_rw_own" on public.user_data_export using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- updated_at-Trigger (Funktion aus 0001)
drop trigger if exists alert_settings_touch on public.user_alert_settings;
create trigger alert_settings_touch before update on public.user_alert_settings
  for each row execute function public.touch_updated_at();
drop trigger if exists fees_touch on public.success_fee_charges;
create trigger fees_touch before update on public.success_fee_charges
  for each row execute function public.touch_updated_at();
