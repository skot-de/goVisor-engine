-- Ein Schreibweg auf den Profil-Blob, ohne Lese-Ändere-Schreibe-Zyklus (2026-09-17).
--
-- WARUM. `user_profiles.profile` (jsonb) wurde von ZWEI Stellen geschrieben, beide nach
-- demselben Muster: Blob lesen, im Client verändern, ganzen Blob zurückschreiben.
--
--     lib/supabase/auth.ts        saveProfile   — Passung, Regionen, Wertspanne
--     lib/supabase/unternehmen.ts patchProfil   — Eignungsangaben (#27), Historie
--
-- Zwischen Lesen und Schreiben liegt ein Fenster. Schreibt die andere Stelle darin, ist
-- ihre Änderung weg — der spätere Schreiber trägt den Stand von vor ihr. `patchProfil`
-- trug dazu den Kommentar „Verhindert Lost-Updates zwischen Sektionen"; das stimmte nur
-- gegen sich selbst.
--
-- Einmal zugeschlagen hat es am 2026-09-17 im Onboarding: `saveProfile` und die Übernahme
-- des Eignungs-Checks liefen nebenläufig, der spätere gewann, und der Nutzer sah
-- „0 von 7.013". Dort wurden die Aufrufe gereiht — das behebt den einen Fall, nicht die
-- Fehlerklasse.
--
-- WAS DIESE FUNKTION ÄNDERT. Der Merge passiert in EINER Anweisung in der Datenbank.
-- Es gibt kein Fenster mehr, in dem ein zweiter Schreiber dazwischenkommen könnte.
--
-- ⚠ `||` MISCHT FLACH. Ein Schlüssel im Patch ersetzt den gleichnamigen im Blob
-- vollständig; verschachtelte Objekte werden NICHT rekursiv gemischt. Das ist hier
-- richtig: die Aufrufer schicken genau die Felder, die sie ändern wollen, und ein Feld
-- gehört immer genau einem von ihnen. Wer das ändert, muss diesen Satz neu prüfen.
--
-- ⚠ EIN FELD LÖSCHEN heißt `{"feld": null}` schicken, nicht das Feld weglassen. Ein
-- weggelassenes Feld bleibt unverändert stehen — das ist der Sinn des Merges.

create or replace function public.merge_profile(p_patch jsonb)
returns void
language plpgsql
security invoker           -- RLS gilt weiter; die Zeile gehört dem aufrufenden Nutzer
set search_path = public
as $$
begin
  if p_patch is null or jsonb_typeof(p_patch) <> 'object' then
    raise exception 'merge_profile: p_patch muss ein JSON-Objekt sein';
  end if;
  update public.user_profiles
     set profile = coalesce(profile, '{}'::jsonb) || p_patch
   where id = auth.uid();
end;
$$;

revoke all on function public.merge_profile(jsonb) from public;
grant execute on function public.merge_profile(jsonb) to authenticated;

comment on function public.merge_profile(jsonb) is
  'Mischt einen Patch atomar in user_profiles.profile. Ersetzt den Lese-Ändere-Schreibe-'
  'Zyklus aus auth.ts und unternehmen.ts (2026-09-17).';
