-- Merkliste behält Titel und Käufer (Aktivierung C, 2026-09-01).
--
-- WARUM. `export_web_leads.py` wirft offene Ausschreibungen mit abgelaufener echter Frist aus
-- dem Frontend-Export („nicht mehr biet-bar → raus aus der Akquise-Liste"). Ein gemerkter
-- Vorgang verschwand damit am Tag nach der Frist SPURLOS: die Zeile in `user_watchlist` blieb
-- stehen, der Inhalt war weg, und niemand konnte mehr sagen, worum es ging.
--
-- Genau dieser Moment trägt die wertvollste Frage, die wir stellen können: „habt ihr
-- mitgeboten?". Die Bieterzahl steht in keiner Bekanntmachung, sie entsteht nur, wenn jemand
-- sie uns sagt. Ohne Titel und Käufer lässt sich die Frage nicht stellen.
--
-- ⚠ DIESELBE ENTSCHEIDUNG WIE BEI `user_outcomes`, und aus demselben Grund: dort steht seit
-- Ticket #11 „denormalisierter Kontext für die private Bilanz (kein Join nötig, kein
-- Aggregat-Rückfluss)". Ein Join gegen den Lead geht ja gerade nicht mehr — er ist weg.
--
-- ⚠ NUR FÜR NEUE EINTRÄGE. Bestehende Zeilen bleiben ohne Titel; ihnen fehlt der Kontext
-- rückwirkend, und erfinden lässt er sich nicht. Die Anzeige fällt dann auf „(ohne Titel)"
-- zurück, statt eine Zeile zu verschweigen.

alter table public.user_watchlist
  add column if not exists titel text,
  add column if not exists buyer_name text;

comment on column public.user_watchlist.titel is
  'Titel zum Zeitpunkt des Merkens. Nötig, weil abgelaufene Vorgänge aus dem Frontend-Export fallen.';
comment on column public.user_watchlist.buyer_name is
  'Vergabestelle zum Zeitpunkt des Merkens, siehe titel.';
