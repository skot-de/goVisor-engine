-- 0039 — Ein Dokument-Teil darf seine Quelle verlieren, ohne das Loeschen zu blockieren.
--
-- ⚠ FEHLER AUS 0038, gefunden beim ersten Durchlauf von Hand und nicht von einem Test.
--
-- 0038 wollte zweierlei gleichzeitig:
--   1. `baustein_id` mit `on delete set null` — ein geloeschter Baustein soll keinen Absatz aus
--      einem fertigen Dokument entfernen, der Teil bleibt stehen und meldet die fehlende Quelle.
--   2. die Bedingung `teil_form`, die fuer `art = 'baustein'` ein `baustein_id is not null`
--      verlangte.
--
-- Beides zusammen ist ein Widerspruch: das `set null` erzeugt genau die Zeile, die die Bedingung
-- verbietet. Das Loeschen schlaegt deshalb fehl, nicht der Verweis:
--
--     23514  new row for relation "profile_dokument_teil" violates check constraint "teil_form"
--
-- **Die Folge war schlimmer als der Fehler aussieht: ein Baustein, der in irgendeinem Dokument
-- steckt, haette sich NIE WIEDER loeschen lassen** — und zwar mit einer Meldung, die von einer
-- ganz anderen Tabelle spricht. Wer seine Bibliothek aufraeumen will, haette nicht verstanden,
-- warum er es nicht darf.
--
-- Richtig ist: ein Baustein-Teil traegt **keinen eigenen Text** — ob er seine Quelle noch hat,
-- ist eine andere Frage. `baustein_id is null` heisst dann „verwaist", und die Oberflaeche zeigt
-- das (`quelle_fehlt`, s. `web/app/api/dokument/route.ts`).

alter table public.profile_dokument_teil drop constraint if exists teil_form;

alter table public.profile_dokument_teil add constraint teil_form check (
  -- Ein Baustein-Teil hat nie eigenen Text. `baustein_id` DARF null sein: dann ist er verwaist.
  (art = 'baustein' and inhalt_encrypted is null)
  -- Ueberschrift und Text tragen eigenen Inhalt und zeigen auf keinen Baustein.
  or (art in ('ueberschrift', 'text') and baustein_id is null and inhalt_encrypted is not null)
);

comment on constraint teil_form on public.profile_dokument_teil is
  'Baustein-Teil: kein eigener Text, baustein_id darf null sein (verwaist, s. 0039). '
  'Ueberschrift und Text: eigener Inhalt, kein Verweis.';
