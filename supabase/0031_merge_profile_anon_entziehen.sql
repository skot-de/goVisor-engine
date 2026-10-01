-- Hygiene, kein Loch: `anon` das EXECUTE auf merge_profile entziehen.
--
-- ⚠ ZUR EINORDNUNG, damit das hier nicht groesser klingt als es ist. 0030 schloss eine echte
-- Luecke: `kauf_gutschreiben` ist `security definer` und nimmt die Organisation als PARAMETER
-- — mit dem oeffentlichen anon-Key waren damit Sitzplaetze ohne Zahlung gutschreibbar.
--
-- `merge_profile` ist anders gebaut und war NICHT ausnutzbar, doppelt abgesichert:
--   1. `security invoker` — die Funktion laeuft mit den Rechten des Aufrufers, nicht des
--      Eigentuemers. Fuer `anon` ist `auth.uid()` NULL, beide UPDATE-Zweige treffen
--      `where id = NULL` und damit keine Zeile.
--   2. Die Policy `profiles_update_own` (0001) verlangt `auth.uid() = id`; NULL = NULL ist
--      nicht wahr, also greift auch RLS.
--
-- Entzogen wird es trotzdem, aus zwei Gruenden: die ABSICHT steht schon da (0025 gewaehrt
-- ausdruecklich nur `authenticated`), und ein unbeabsichtigtes Recht ist der Zustand, aus dem
-- die naechste Luecke entsteht — es muss nur jemand `security invoker` zu `definer` aendern
-- oder eine Policy weiter fassen, und aus der Hygiene wird ein Befund.
--
-- Gefunden von `tests/test_rpc_rechte.py`, das aus dem 0030-Befund entstanden ist.
-- Idempotent.

revoke all on function public.merge_profile(jsonb) from public, anon;
grant execute on function public.merge_profile(jsonb) to authenticated;
