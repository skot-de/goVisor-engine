-- goVisor: Erfolgsprämie aus dem Produkt entfernen (2026-08-21)
-- Anwenden:  Supabase Dashboard → SQL Editor  (DDL laeuft in diesem Projekt nur dort)
--
-- WARUM. Das Erfolgsprämien-Modell war nie scharf: kein Stripe-Key, kein Rechnungslauf,
-- keine Kalkulation. Uebrig waren eine leere Tabelle, eine Schonfrist-Spalte und ein
-- Dutzend Oberflaechentexte, die Nutzern eine Abrechnung versprachen, die es nicht gibt.
-- Der Code ist am 2026-08-21 bereinigt, diese Migration raeumt das Schema hinterher.
--
-- ⚠ NICHT BLIND AUSFUEHREN. Der Block unten bricht ab, wenn in success_fee_charges auch
-- nur eine Zeile steht. Rechnungsdaten sind personenbezogen und aufbewahrungspflichtig;
-- die duerfen nicht als Nebenwirkung eines Aufraeumzugs verschwinden. Gibt es Zeilen,
-- erst exportieren und die Loeschung bewusst entscheiden, dann das `raise` streichen.

do $$
declare n bigint;
begin
  if to_regclass('public.success_fee_charges') is null then
    raise notice 'success_fee_charges existiert nicht — nichts zu tun.';
  else
    execute 'select count(*) from public.success_fee_charges' into n;
    if n > 0 then
      raise exception 'ABBRUCH: % Zeile(n) in success_fee_charges. Erst exportieren, dann bewusst loeschen.', n;
    end if;
    drop trigger if exists fees_touch on public.success_fee_charges;
    drop policy  if exists "fees_select_own" on public.success_fee_charges;
    drop table   public.success_fee_charges;
    raise notice 'success_fee_charges entfernt (war leer).';
  end if;
end $$;

-- Erfolgsprämien-Schonfrist. Reine Ableitung aus dem Praemienmodell, ohne eigenen Wert.
alter table public.user_profiles drop column if exists grace_until;
