-- Preismodell v1.9 §7.1 — Nutzer × Unternehmensprofil (m:n). Baut auf 0024/0025 auf.
--
-- WARUM. Bisher darf jedes Mitglied JEDES Profil seiner Org sehen und aktiv schalten
-- (profiles_select_member, 0024). §7.1 verlangt die feinere Zuordnung: „je Nutzer einem ODER
-- MEHREREN Profilen zugeordnet". Das ist die Voraussetzung fuer §7.2 (Ebene-B-Trennung
-- zwischen Konzern-Einheiten): ein Nutzer, der nur Profil A fuehrt, darf Profil B nicht nutzen.
--
-- ⚠ `active_profile_id` BLEIBT „genau EIN aktives Profil" (0024). Diese Tabelle sagt nur, WELCHE
-- Profile ein Nutzer ueberhaupt waehlen darf; die Aktiv-Weiche in auth.ts bleibt unberuehrt.
--
-- ⚠ RLS-FALLE, bewusst geloest: eine Policy, die quer ueber `user_profiles` eines ANDEREN
-- Nutzers liest, bekommt durch dessen RLS NULL und schlaegt still fehl. Darum: die SELECT-
-- Policy deckt nur die EIGENEN Zuordnungen (fuer Umschalter/Liste unter der Nutzer-Session);
-- die owner/admin-Verwaltung ueber die ganze Org laeuft im Code ueber den Admin-Client
-- (createAdminClient), genau wie /api/org/mitglieder. Deshalb KEINE Client-Schreib-Policy.

create table if not exists public.user_profile_assignments (
  user_id    uuid not null references public.user_profiles(id) on delete cascade,
  profile_id uuid not null references public.profiles(id)      on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, profile_id)
);
create index if not exists upa_profile_idx on public.user_profile_assignments (profile_id);

alter table public.user_profile_assignments enable row level security;
-- Nur die EIGENEN Zuordnungen (reicht fuer „welche Profile darf ich waehlen"). Owner/Admin
-- lesen/schreiben org-weit ueber den Admin-Client, nicht ueber RLS.
drop policy if exists "upa_select_own" on public.user_profile_assignments;
create policy "upa_select_own" on public.user_profile_assignments for select
  using (user_id = auth.uid());

-- ── Backfill: jeden bestehenden Nutzer seinem AKTIVEN Profil zuordnen ──────────────────────
-- Verlustfrei: heute hat jede Org genau ein Profil = das aktive. Niemand verliert Zugang.
insert into public.user_profile_assignments (user_id, profile_id)
  select id, active_profile_id from public.user_profiles where active_profile_id is not null
  on conflict do nothing;

-- Selbstpruefung: jeder Nutzer mit aktivem Profil hat die Zuordnung zu GENAU diesem Profil.
-- Ein halber Backfill (ein Nutzer koennte sein eigenes aktives Profil nicht mehr waehlen) ist
-- damit unmoeglich.
do $$
declare n int;
begin
  select count(*) into n from public.user_profiles up
   where up.active_profile_id is not null
     and not exists (select 1 from public.user_profile_assignments a
                     where a.user_id = up.id and a.profile_id = up.active_profile_id);
  if n > 0 then
    raise exception 'Backfill unvollstaendig: % Nutzer ohne Zuordnung ihres aktiven Profils', n;
  end if;
end $$;
