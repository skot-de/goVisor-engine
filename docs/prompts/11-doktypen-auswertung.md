# Erkannt, einschlaegig, nicht ausgewertet: 4.835 Vorgaenge

## Der Befund

`scripts/analyze_docs.py` wertet nur Dokumente aus, deren Doktyp in `AUSWERTUNG` steht:

    aufforderung · eignung · fragenantworten · leistungsbeschreibung · vertrag · zuschlagskriterien

Alles andere landet in `other_documents` („Weitere Dokumente", §7.5) und wird nie gelesen.
`govisor/doctypes.py` erkennt aber mehr Typen als diese sechs — und zwei davon tragen
genau das, wofuer das Produkt gebaut ist.

Gemessen am 2026-09-18 ueber alle 11.144 Auswertungen (100.215 Dateien in
`other_documents`):

    Dateien   Vorgaenge   Doktyp
     51.616      8.404    sonstiges              zu Recht
     17.874      3.405    technische_anlage      Plaene, Ansichten, Lageplaene — zu Recht
     13.131      4.835    eigenerklaerung        ⚠ traegt Eignungsanforderungen
      5.396      3.836    informationsblatt      ⚠ z. B. „Wichtige Hinweise zu
                                                    Sicherheitsleistungen"
      5.087      4.256    datenschutz            zu Recht
      3.194      2.143    preisblatt             offen
      2.986      1.823    formblatt              ⚠ vermutlich einschlaegig

Konkrete Beispiele, durch `doctypes.classify()` gefahren:

    eigenerklaerung    315 26 A14 Bietergemeinschaftserklaerung.pdf
    eigenerklaerung    Formblatt 124 Eigenerklaerung Nachunternehmer.pdf
    informationsblatt  02_Wichtige Hinweise zu Sicherheitsleistungen.pdf

Eine Bietergemeinschaftserklaerung sagt, ob man als Gemeinschaft bieten darf. Ein Blatt
ueber Sicherheitsleistungen nennt die Buergschaft. Beides steht heute in keinem Profil.

## Wie es aufgefallen ist

Nicht durch eine Sonde, sondern beim Nachgehen einer anderen Zahl. `pruefe-dichte.mjs`
meldete 421 Leads mit Volltext ohne verwertbaren Inhalt. Davon:

    385   Auswertung laeuft noch — eine Warteschlange, kein Fehler
     35   einziges Dokument ist die Bekanntmachung selbst — zu Recht nichts zu holen
      1   Auswertung mit Dokumenten, aber ohne Anforderungen

Die 421 waren also harmlos. Beim Aufschluesseln fiel auf, dass 1.525 der 11.144
Auswertungen (13,7 %) GAR KEIN ausgewertetes Vergabedokument haben — und von dort fuehrte
die Spur zu `AUSWERTUNG`.

## ⚠ Was das kostet, bevor jemand die Liste erweitert

`AUSWERTUNG` zu erweitern heisst: das LLM liest 13.131 (bzw. 18.527) Dokumente mehr. Das
ist kein Schalter, das ist Geld.

**Vor dem Umbau zu klaeren, in dieser Reihenfolge:**

1. **Was kostet ein Dokument?** `token_cost` steht in jeder Analyse-Datei. Daraus einen
   Mittelwert ziehen und hochrechnen — die Zahl gehoert in den Auftrag, nicht in die
   Rueckschau. `memory/govisor-geldwache.md`: die Bremse sitzt in `llm.chat()`, nicht im
   Aufrufer.
2. **Bringt es etwas?** Eine Stichprobe von 20 `eigenerklaerung`-Dokumenten von Hand
   durchsehen: wie viele tragen eine Anforderung, die nicht schon aus `eignung` kommt?
   Wenn die Eigenerklaerung nur wiederholt, was die Aufforderung sagt, ist der Gewinn null
   und die Kosten sind echt.
3. **Reicht ein Teil?** `formblatt` und `preisblatt` sind unklar; `datenschutz` und
   `technische_anlage` sind es nicht. Wer alles aufnimmt, zahlt fuer Plaene.

## ⚠ Eine zweite Auffaelligkeit, kleiner, aber unerklaert

254 Dateien in `other_documents` klassifizieren ueber den NAMEN als `fragenantworten`,
211 als `aufforderung`, 174 als `leistungsbeschreibung` — alle drei stehen in
`AUSWERTUNG`. Sie haetten also ausgewertet werden muessen.

Die wahrscheinliche Erklaerung: `analyze_docs` ruft `classify(name, text)` MIT der
Inhaltsprobe, meine Messung nur mit dem Namen. Die Inhaltsprobe hat dann anders
entschieden. Das kann richtig sein (der Name luegt) oder falsch (die Probe traf eine
Deckblattseite). ⚠ Das ist zu pruefen, bevor man an `AUSWERTUNG` dreht — sonst behebt man
die falsche Haelfte.

## Abnahme

- Kostenschaetzung je zusaetzlichem Doktyp, aus `token_cost` gerechnet, im Commit.
- Stichprobe von 20 Dokumenten je aufgenommenem Typ, handgeprueft, mit Ergebnis.
- Zahl der Vorgaenge mit `anf.quelle=unterlagen` vorher/nachher — das ist der Beleg.
- ⚠ `pruefe-dichte.mjs` muss danach weiter gruen sein: mehr ausgewertete Dokumente heissen
  mehr Leads, die „reich" behaupten, und die Invariante gegen `unterlagen.gelesen` gilt
  unveraendert.
