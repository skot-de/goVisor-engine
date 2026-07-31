-- goVisor Ticket #23 — Vergabeunterlagen-Analyse & Bausteinbibliothek (§13 Datenmodell).
-- Zwei Ebenen mit STRIKTER Rechtetrennung (§3, §12.1):
--   Ebene A (doc_*)      — verfahrensspezifische Checklisten, lesbar für alle authentifizierten
--                          Nutzer desselben Leads, SCHREIBBAR NUR über die Systemrolle (Secret-Key,
--                          umgeht RLS) → keine insert/update-Policy.
--   Ebene B (profile_*)  — Firmentexte des Nutzers, ausschließlich eigenes Profil (RLS profilgebunden),
--                          Inhalt verschlüsselt (§12.3, Chiffrat in der DB).
-- Originaldokumente werden NIE persistiert — nur Hashes, Metadaten, Extraktionsergebnisse (§13).
-- Idempotent. Anwenden: psql "$CONN" -f supabase/0006_doc_analysis.sql

-- ══ Ebene A — verfahrensspezifisch (Systemrolle schreibt, alle authentifizierten lesen) ══

-- Semantische Anforderungs-Taxonomie (§3, §6a.1) — Referenz, kein Textcache. Deckt sich mit govisor/doctax.py.
create table if not exists public.doc_requirement_types (
  req_type text primary key,                 -- z. B. referenz_mindestwert, zertifikat, frist
  label    text not null,
  theme    text not null                     -- Bausteine-Thema (§9.4)
);

-- Hochgeladenes Paket je Lead (§13). package_hash = Dedup + Herkunft (§5-5, §12.2).
create table if not exists public.doc_packages (
  id             uuid primary key default gen_random_uuid(),
  lead_id        text not null,
  package_hash   text not null,              -- stabiler Hash (govisor.docupload.package_hash)
  doc_state_date date,                       -- Stand der Unterlagen (§7.3)
  file_count     int  not null default 0,
  token_cost     int  not null default 0,    -- LLM-Verbrauch je Analyse (§6.3)
  rejected_items int  not null default 0,    -- Verwerfungsquote (§6a.2) — laufende Qualitätskennzahl
  visibility     text not null default 'private' check (visibility in ('private','shared')),  -- §12.2
  uploaded_by    uuid references public.user_profiles(id) on delete set null,
  created_at     timestamptz not null default now(),
  unique (lead_id, package_hash)             -- ein Paket je Lead nur einmal (§5-5, §12.6)
);

create table if not exists public.doc_files (
  id          uuid primary key default gen_random_uuid(),
  package_id  uuid not null references public.doc_packages(id) on delete cascade,
  filename    text not null,
  doctype     text,                          -- govisor/doctypes.py-Klassifikation
  hash        text,                          -- Inhalts-Hash (Original nicht gespeichert)
  pages       int,
  parser_used text                           -- gaeb|pdf_fields|xlsx|null (§6.2)
);

create table if not exists public.doc_checklists (
  id         uuid primary key default gen_random_uuid(),
  lead_id    text not null,
  lot_id     text,                           -- nullable: Los-Abschnitt (§8)
  package_id uuid references public.doc_packages(id) on delete set null,
  status     text not null default 'ready',
  created_at timestamptz not null default now()
);

create table if not exists public.doc_checklist_items (
  id           uuid primary key default gen_random_uuid(),
  checklist_id uuid not null references public.doc_checklists(id) on delete cascade,
  req_type     text references public.doc_requirement_types(req_type),
  theme        text,
  value        text,
  unit         text,
  quote        text,                          -- wörtliches Zitat (Belegpflicht §6a.2)
  source_file  text,
  source_page  int,
  marking      text check (marking in ('Zitat','Extrahiert','Abgeleitet')),  -- §7.2
  lot_ref      text
);

alter table public.doc_requirement_types enable row level security;
alter table public.doc_packages          enable row level security;
alter table public.doc_files             enable row level security;
alter table public.doc_checklists        enable row level security;
alter table public.doc_checklist_items   enable row level security;

-- Ebene A: lesbar für alle authentifizierten (Wiederverwendung innerhalb eines Leads, §3);
-- KEINE write-Policy → nur die Systemrolle (Secret-Key) schreibt. Sichtbar erst ab visibility='shared'
-- (Bestätigungsschwelle §12.2) — die private Phase filtert der Server, nicht die Policy.
drop policy if exists "docreq_read" on public.doc_requirement_types;
create policy "docreq_read" on public.doc_requirement_types for select to authenticated using (true);
drop policy if exists "docpkg_read" on public.doc_packages;
create policy "docpkg_read" on public.doc_packages for select to authenticated using (visibility = 'shared');
drop policy if exists "docfiles_read" on public.doc_files;
create policy "docfiles_read" on public.doc_files for select to authenticated using (
  exists (select 1 from public.doc_packages p where p.id = package_id and p.visibility = 'shared'));
drop policy if exists "docchk_read" on public.doc_checklists;
create policy "docchk_read" on public.doc_checklists for select to authenticated using (true);
drop policy if exists "docitem_read" on public.doc_checklist_items;
create policy "docitem_read" on public.doc_checklist_items for select to authenticated using (true);

-- ══ Ebene B — Firmentexte (profilgebunden, verschlüsselt) ══
-- V1: profile_id = Konto (user_profiles.id). Firma-weite Mehrbenutzer-Freigabe ist eine spätere
-- Verfeinerung (§9.1 „zuletzt bearbeitet von"); das Feld last_edited_by hält die Zuschreibung bereit.
create table if not exists public.profile_text_blocks (
  id               uuid primary key default gen_random_uuid(),
  profile_id       uuid not null references public.user_profiles(id) on delete cascade,
  theme            text not null,             -- feste Themen-Taxonomie (§9.4)
  content_encrypted bytea not null,           -- Envelope-Verschlüsselung (§12.3) — nur Chiffrat
  keywords         text[],                    -- abgeleitet, nutzer-korrigierbar (§9.3)
  origin           text,                      -- Herkunft (z. B. Import-Metadaten §10.2)
  outcome          text check (outcome in ('erfolgreich','nicht_erfolgreich') or outcome is null),  -- §10.4 neutral
  archived         boolean not null default false,   -- Archivieren statt Löschen (§9.2)
  last_edited_by   uuid references public.user_profiles(id) on delete set null,
  updated_at       timestamptz not null default now()
);

create table if not exists public.profile_block_usage (
  id       uuid primary key default gen_random_uuid(),
  block_id uuid not null references public.profile_text_blocks(id) on delete cascade,
  lead_id  text not null,
  used_at  timestamptz not null default now()
);

alter table public.profile_text_blocks enable row level security;
alter table public.profile_block_usage enable row level security;
-- Ebene B: ausschließlich eigenes Profil (§9.1, §12.3 Mandantentrennung).
drop policy if exists "ptb_rw_own" on public.profile_text_blocks;
create policy "ptb_rw_own" on public.profile_text_blocks
  using (auth.uid() = profile_id) with check (auth.uid() = profile_id);
drop policy if exists "pbu_rw_own" on public.profile_block_usage;
create policy "pbu_rw_own" on public.profile_block_usage using (
  exists (select 1 from public.profile_text_blocks b where b.id = block_id and b.profile_id = auth.uid()));

-- Taxonomie-Seed (aus govisor/doctax.py; idempotent).
insert into public.doc_requirement_types (req_type, label, theme) values
  ('mindestumsatz','Mindestumsatz','unternehmensdarstellung'),
  ('referenz_anzahl','Mindestanzahl vergleichbarer Referenzen','referenzen'),
  ('referenz_mindestwert','Referenz-Mindestwert','referenzen'),
  ('zertifikat','Gefordertes Zertifikat / Nachweis','zertifikate_qm'),
  ('ausschlussgrund','Ausschluss-/Mindestbedingung','sonstiges'),
  ('eignung_technisch','Technische Mindesteignung','technische_ausstattung'),
  ('eignung_personal','Personelle Eignung / Qualifikation','personal_qualifikation'),
  ('berufshaftpflicht','Berufs-/Betriebshaftpflicht-Deckung','unternehmensdarstellung'),
  ('zuschlagskriterium','Zuschlagskriterium mit Gewicht','projektorganisation'),
  ('leistung_menge','Leistungsumfang / Menge','sonstiges'),
  ('technische_mindestanforderung','Technische Mindestanforderung','technische_ausstattung'),
  ('vertragsstrafe','Vertragsstrafe','sonstiges'),
  ('haftung','Haftungsregelung','sonstiges'),
  ('laufzeit','Laufzeit / Verlängerungsoption','sonstiges'),
  ('kuendigung','Kündigungsrecht','sonstiges'),
  ('frist','Frist','sonstiges'),
  ('einzureichendes_dokument','Einzureichendes Dokument / Anlage','sonstiges'),
  ('formalie','Formalie','sonstiges')
on conflict (req_type) do update set label = excluded.label, theme = excluded.theme;
