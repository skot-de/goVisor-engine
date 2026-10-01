-- Sicherheitshaertung: EXECUTE auf den service-only RPCs auf service_role beschraenken.
--
-- ⚠ BEFUND 2026-10-01. Supabase gewaehrt neuen Funktionen im Schema `public` per
-- ALTER DEFAULT PRIVILEGES automatisch EXECUTE an `anon` UND `authenticated`. Ein
-- `revoke all ... from public` (wie in 0027/0029) entfernt diese EINZEL-Grants NICHT — die
-- Funktionen blieben fuer jeden mit dem (oeffentlichen) anon-Key direkt aufrufbar.
--
-- Konkrete Luecke, die das schliesst:
--   * `kauf_gutschreiben` (0027): ein Client haette sich `kauf_gutschreiben(<org>, 'seat',
--     100, 'stripe', '<beliebig>')` selbst gutschreiben koennen — Seats/Profile OHNE Zahlung.
--   * `vorgang_freischalten` (0029): Aufruf mit beliebigem p_limit haette das Free-Monatslimit
--     umgangen.
--
-- Beide werden ausschliesslich serverseitig ueber den Service-Key gerufen (lib/kauf.ts,
-- lib/vorgang.ts). service_role behaelt EXECUTE (eigener Grant, vom Entzug unberuehrt).
-- Idempotent.

revoke all on function public.kauf_gutschreiben(uuid,text,int,text,text,int,text)
  from public, anon, authenticated;
revoke all on function public.vorgang_freischalten(uuid,text,text,int,uuid)
  from public, anon, authenticated;

-- Sicherstellen, dass der legitime Aufrufer die Rechte behaelt (no-op, falls schon vorhanden).
grant execute on function public.kauf_gutschreiben(uuid,text,int,text,text,int,text) to service_role;
grant execute on function public.vorgang_freischalten(uuid,text,text,int,uuid) to service_role;
