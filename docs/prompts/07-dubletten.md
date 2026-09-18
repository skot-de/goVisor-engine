# Dubletten: die vorgeschlagene Loesung war falsch

## Was der Auftrag sagte

> Die paarweisen Marken zu Clustern schliessen (Union-Find oder gleichwertig), statt je
> Paar zu entscheiden.

**Gemessen am 2026-09-17: das haette tausende echte Vergaben geloescht.**

## Warum

Union-Find ueber alle 115.044 DE-Paare ergibt 22.611 Cluster — und das groesste hat
**4.720 Knoten mit 923 verschiedenen Titeln**: „Anbau Grundschule Affaltrach",
„Zeitvertragsarbeiten", „Heizung, Lueftung, Sanitaer". Das ist kein Vorgang, das ist ein
Klumpen, der ueber generische Gewerke-Titel zusammenkettet.

Die Ursache steht seit jeher im Code (`govisor/dedupe.py`):

> Ein kurzer Gewerke-Titel („Sanitär, Lüftung, Heizung") steckt vollständig in jedem
> längeren Titel desselben Gewerks — Enthaltung 1,0 ist dort KEIN Identitätsbeleg.

Deshalb traegt jedes Paar eine BELEGSTUFE:

    geschwister         39.582   Lose desselben Vorgangs (und Fremdes desselben Kaeufers)
    nur_titel_kurz      38.855   nur ein kurzer Titel — die Klumpenbildner
    kaeufer_und_titel   34.418   Kaeufer UND Titel — die belastbare Stufe
    nur_titel            2.189

Und `gold.py` schliesst ausdruecklich nur auf `kaeufer_und_titel` aus. **Die Firewall war
vorsichtiger als der Auftrag annahm.** Clustert man nur ueber die belastbare Stufe,
schrumpft das groesste Cluster von 4.720 auf 146.

## Was WIRKLICH offen ist

### (a) Datumslose Paare — BEHOBEN am 2026-09-17

Die ±90-Tage-Regel ist die erste der drei gemessenen Regeln der Firewall. Gemessen:

    Paare MIT Datum    96.713   ausnahmslos <= 90 Tage (Median 27, Maximum exakt 90)
    Paare OHNE Datum   18.331   15,9 % — nie geprueft
      davon `kaeufer_und_titel`: 361, und genau die schlossen Leads aus

`_in_zeitscheiben` laesst datumslose Saetze bewusst in JEDER Zeitscheibe mitlaufen („sie
koennen mit allem paaren"). Als Kandidatenregel ist das richtig; als Beleg ist es etwas
anderes — ein solches Paar hat die Hauptbedingung nicht bestanden, sondern uebersprungen.

Beispiel: „Neubau Optical Imaging Center- OIC." (2017) wurde mit „E94.1 OIC - Neubau
Optical Imaging Center/VE 4.11 Montageschienen" gepaart. Dasselbe Bauprojekt, sechs Jahre
und eine andere Vergabeeinheit auseinander. Von 68 Vorgaengen dieses Projekts sind rund 60
eigenstaendige Gewerke.

⚠ **Nicht alle datumslosen Paare sind schlecht.** Die Wortmenge trennt sie sauber:

    identische Titel        111   „SPA Loessnig, Sanierung Rundlaufbahn" doppelt
    eine enthaelt die andere 255   „Erweiterung Stadtbad Plauen - Los VM 004 -
                                    Abbrucharbeiten" gegen „Erweiterung Stadtbad Plauen"

Identische Titel bei identischem Kaeufer sind auch ohne Datum ein Beleg — der Abstand
haette daran nichts mehr zu entscheiden. Eine Enthaltung dagegen ist genau der Fall, den
die 90 Tage abfangen sollen: dieselbe Baustelle, anderes Los, Jahre spaeter.

Behoben: eigene Stufe `kaeufer_und_titel_ohne_datum`, aber NUR fuer die enthaltenen.
Nicht verworfen, nur markiert — wie im Rest der Firewall.

    Paare auf der neuen Stufe                          248
    datumslose Paare, die bewusst belastbar bleiben    118   ← kein Restfehler

⚠ **Die Wirkung erreicht die Oberflaeche erst mit dem naechsten Nachtlauf.** Geaendert ist
`data/gold/DE/notice_duplicates.parquet`; `web/data/leads-*.json` entsteht erst im Export.

### (b) Ketten-Cluster — URSACHE GEFUNDEN, BEHOBEN am 2026-09-18

Die Frage war: warum FEHLEN Kanten? Drei identische OIC-Ankuendigungen paarten nicht
miteinander. Die Antwort steht in `_paare_finden`:

    if s["gen"] == t["gen"]:
        continue      # dieselbe Quelle dedupliziert sich selbst schon

Alle drei sind `legacy` — dieselbe Quelle. Sie KONNTEN einander per Konstruktion nie
finden. Deshalb lag keiner der 4.637 ueberzaehligen Vorgaenge in einem vollstaendigen
Cluster: die Kanten innerhalb einer Quelle gab es nie. Die Annahme stimmt nicht, eForms
und TED veroeffentlichen Korrekturen als eigene Bekanntmachung.

Gemessen ueber die DE-Ausschreibungen ab 2025:

    identischer Titel + Kaeufer + Stufe, <= 90 Tage, DIESELBE Quelle   77.341
      davon stehen BEIDE in der ausgelieferten Liste                    8.797

⚠ **Die Schwierigkeit ist die Serie, nicht die Dublette.** Vier Belege zusammen plus ein
Gruppendeckel trennen sie (s. `dedupe._wiederholung`). Ergebnis: 17.173 Paare, davon 9
aus der 219er-Rabatt-Serie; Wirkung auf die heutige Liste 527 Paare von 43.683 Leads.

## Was NICHT hilft

- Union-Find ueber alle Paare (s. oben).
- Die Enthaltungsschwelle anheben: gemessen bringt 0,90 → 1,0 keinen Unterschied
  (75.462 Paare in beiden Faellen), weil die Klumpenbildner exakt 1,0 erreichen. Genau
  davor warnt der Kommentar in `dedupe.py`.
