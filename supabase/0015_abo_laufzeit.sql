-- goVisor: Abo-Ende festhalten, damit „gekündigt" nicht „sofort gesperrt" heisst
-- Anwenden:  python3 scripts/migrate.py supabase/0015_abo_laufzeit.sql
--
-- WARUM. `user_profiles.plan` kennt 'free' | 'paid' | 'cancelled', aber kein Datum. `getTier`
-- musste `cancelled` deshalb wie `free` behandeln: wer am 2. des Monats kündigt, verliert den
-- bezahlten Zugang noch am selben Tag, obwohl er den Monat bezahlt hat. Das fällt erst auf,
-- wenn es einem Kunden passiert — und dann ist es eine Rückbuchung wert.
--
-- Bewusst additiv und ohne Vorgabewert: NULL heisst „kein Enddatum bekannt", und genau so
-- liest `getTier` es auch. Bestehende Zeilen ändern ihr Verhalten dadurch nicht.

alter table public.user_profiles
  add column if not exists plan_until timestamptz;

comment on column public.user_profiles.plan_until is
  'Ende des bezahlten Zeitraums. Bei plan=''cancelled'' gilt Pro bis zu diesem Zeitpunkt; '
  'NULL = kein Enddatum bekannt, dann endet der Zugang sofort.';
