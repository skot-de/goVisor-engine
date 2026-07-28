-- goVisor — profile_type: der rollen-agnostische Anker (Architekturprinzip §6).
-- „Ein Kern, zwei Profile": Anbieter (bidder) vs. Vergabestelle (contracting_authority).
-- Heute nutzt nur 'bidder'; die Spalte JETZT einzuziehen kostet eine Zeile — nach dem
-- Deployment mit Nutzern wäre es eine Migration + Auth-Flow-Änderung. Genau die
-- „billig heute, teuer später"-Sache aus dem Architektur-Dokument.
-- Anwenden:  psql "$CONN" -f supabase/0004_profile_type.sql   (idempotent)

alter table public.user_profiles
  add column if not exists profile_type text not null default 'bidder'
  check (profile_type in ('bidder', 'contracting_authority'));

comment on column public.user_profiles.profile_type is
  'Rolle, bei Registrierung gewählt (Architekturprinzip §3). Steuert Navigation/Defaults/'
  'Sprache — NICHT den Datenzugriff auf Berechnungsebene (die bleibt entity-parametrisiert).';
