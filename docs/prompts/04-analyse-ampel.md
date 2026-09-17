# doc-analysis-index.json: 10.951 ausgewertete Vorgaenge, die niemand sieht

## Was passiert
Die Vergabeunterlagen-Analyse (Ticket 23) laeuft, wertet aus, vergibt eine Ampel und
schreibt das Ergebnis in eine Indexdatei. In der Oberflaeche gibt es keine Stelle, an
der man sieht, welche Ausschreibung ausgewertete Unterlagen hat. Man muss jeden Lead
einzeln oeffnen und nachsehen.

Gefragt waehrend einer Vorfuehrung: „wo sehe ich, welche Ausschreibungen analysierte
Unterlagen haben?" Antwort: nirgends.

## Befund (gemessen 2026-09-17)
    Schreiber : scripts/export_doc_analysis.py
    Leser     : keiner   (grep ueber web/ ohne node_modules, .next → 0 Treffer)

`scripts/pruefe_verdrahtung.py` nennt die Datei, prueft sie aber offenbar nicht als
Fall der eigenen Fehlerklasse. Das ist bemerkenswert, denn genau das ist sie: gebaut,
nicht verdrahtet. Siehe `memory/govisor-verdrahtungspruefung.md`.

Die Datei traegt rund 10.951 Vorgaenge samt Ampel. Die teure Arbeit ist getan.

## Aufgabe
1. Den Index beim Laden der Liste mitziehen und je Lead eine Marke setzen: Unterlagen
   ausgewertet ja/nein, dazu die Ampel.
2. Danach filterbar machen. Der Filter `unterlagen` existiert bereits in `Adv`
   (`FilterPanel.tsx`, Teil der `advCount`-Summe). Pruefe, worauf er heute siebt, bevor
   du einen zweiten daneben baust.
3. Sortierbar nach Informationsdichte, damit die dichtesten Vorgaenge oben stehen.

## Warum das die billigste offene Verbesserung ist
Es entsteht keine neue Rechnung, kein neuer Abruf, kein LLM-Aufruf. Es wird eine Datei
gelesen, die bereits geschrieben wird. Der Aufwand liegt im Zusammenfuehren, nicht im
Erzeugen.

## Fallen
- Die Datei muss ueber `ladeMitGrund` geladen werden, nicht per `readdir` oder direktem
  Plattenzugriff. Auf einem Deployment mit `DATA_BASE_URL` liegt lokal nichts. Der
  Kopf von `web/lib/leadIndex.ts` beschreibt denselben Fehler zweimal, weil er zweimal
  passiert ist.
- Nutzlast pruefen, bevor die Datei in den Erstaufruf wandert. Die Liste laedt heute
  schon zu viel, siehe `docs/prompts/06-ladezustand.md`. Nur die Felder mitnehmen, die
  die Liste braucht: Kennung, Ampel, Zahl der Fundstellen. Nicht die Analysen selbst.
- Sonde in `pruefe_verdrahtung.py` ergaenzen, damit die naechste Datei dieser Art
  auffaellt, bevor jemand in einer Vorfuehrung danach fragt.

## Abnahme
- Zaehle, wie viele Leads der Liste eine Marke bekommen. Die Zahl im Commit.
- Ein Test, der rot wird, wenn der Leser wieder verschwindet.
