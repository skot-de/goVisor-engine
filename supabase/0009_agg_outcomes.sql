-- Feature #11 §9 — Aggregation/Rückspiel der Ergebnismeldungen (DORMANT).
-- Idempotent. Anwenden: psql "$CONN" -f supabase/0009_agg_outcomes.sql
--
-- ⚠️ RECHTLICHE LEITPLANKE (§9.1): Informationsaustausch zwischen Wettbewerbern auf Vergabemärkten
-- ist nach Art. 101 AEUV / § 1 GWB heikel. Diese Tabelle wird erst befüllt und angezeigt, NACHDEM
-- eine kartellrechtliche Prüfung erfolgt ist. Bis dahin:
--   · KEINE Read-Policy für `authenticated` (nur die Service-Rolle sieht die Aggregate).
--   · Der Befüll-Job (scripts/aggregate_outcomes.py) läuft nur mit AGGREGATE_ENABLED=1 und ist
--     NICHT im Tageslauf verdrahtet.
--   · Nur rückwärtsgewandt, aggregiert ab 5 beitragenden Firmen, ohne Anbieterbezug, keine Preise.

create table if not exists public.agg_buyer_outcomes (
  buyer_key        text primary key,      -- normalisierter Vergabestellen-Schlüssel (kein Firmenbezug der Bieter)
  buyer_name       text,
  n_firms          int not null,          -- Zahl beitragender Firmen (≥ 5, sonst kein Eintrag)
  n_participations int not null,
  rank_dist        jsonb,                 -- {rang: anzahl} — anonym, ohne Anbieterbezug
  loss_reasons     jsonb,                 -- {grund: anzahl}
  computed_at      timestamptz not null default now()
);

alter table public.agg_buyer_outcomes enable row level security;
-- BEWUSST keine Policy: solange keine existiert, liest nur die Service-Rolle (RLS blockt authenticated).
-- Nach der Kartellprüfung wird hier eine `for select to authenticated`-Policy ergänzt.
