-- Die Checkliste erbt die Sichtbarkeit ihres Pakets (2026-09-06).
--
-- WARUM. `0006_doc_analysis.sql` setzt die Bestätigungsschwelle aus §12.2 sorgfältig um:
-- `doc_packages` ist auf `visibility = 'shared'` begrenzt, und `doc_files` erbt diese Grenze
-- über einen `exists`-Verweis auf das Paket. Die CHECKLISTE aber — genau der Inhalt, den
-- §12.2 schützen soll — stand auf `using (true)`:
--
--     docchk_read    on doc_checklists       for select to authenticated using (true)
--     docitem_read   on doc_checklist_items  for select to authenticated using (true)
--
-- Damit hätte jeder angemeldete Nutzer JEDE Checkliste lesen können, auch die eines
-- Pakets, das ausdrücklich `private` ist. Der Kern-Risikofall aus §12.2 lautet: „im selben
-- Lead sitzen konkurrierende Bieter". Die Tür am Paket war zu, das Fenster daneben offen.
--
-- ⚠ HEUTE OHNE WIRKUNG, UND GENAU DESHALB JETZT. Gemessen am 2026-09-06: keine der fünf
-- Tabellen aus 0006 wird von einer einzigen Zeile Code gelesen oder geschrieben (ebenso
-- wie `govisor/docsafety.py`, das dieselbe Schwelle rechnet). Es ist also kein Leck,
-- sondern eine Inkonsistenz, die am Tag der Verdrahtung eines wird — und dann in einer
-- Migration von vor Wochen steckt, die niemand mehr liest.
--
-- ⚠ NEUE DATEI STATT ÄNDERUNG AN 0006. Migrationen laufen hier von Hand über den
-- Supabase-Editor; eine bereits eingespielte Datei zu ändern wirkt nirgends.
--
-- `lot_id` und `lead_id` bleiben unberührt: ohne Paket (package_id ist nullable, `on delete
-- set null`) ist eine Checkliste verwaist und wird von niemandem mehr beansprucht — sie
-- bleibt dann für alle unsichtbar. Das ist die sichere Richtung.

drop policy if exists "docchk_read" on public.doc_checklists;
create policy "docchk_read" on public.doc_checklists for select to authenticated using (
  exists (select 1 from public.doc_packages p
          where p.id = package_id and p.visibility = 'shared'));

drop policy if exists "docitem_read" on public.doc_checklist_items;
create policy "docitem_read" on public.doc_checklist_items for select to authenticated using (
  exists (select 1 from public.doc_checklists c
          join public.doc_packages p on p.id = c.package_id
          where c.id = checklist_id and p.visibility = 'shared'));

comment on policy "docchk_read" on public.doc_checklists is
  'Erbt die Sichtbarkeit des Pakets (§12.2). Ohne Paket unsichtbar — die sichere Richtung.';
