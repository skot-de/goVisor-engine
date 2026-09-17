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

### (b) Ketten-Cluster — OFFEN, und NICHT durch Clustern loesbar

Auf der belastbaren Stufe bleiben 2.193 Cluster mit mehr als einem Ueberlebenden,
zusammen 4.637 ueberzaehlige Vorgaenge. Die entscheidende Messung:

    Cluster mit >= 2 Knoten          19.042
      vollstaendig (jede Kante da)   16.367  (86 %)
      nur verkettet                   2.675

    ueberzaehlige Vorgaenge           4.637
      davon in vollstaendigen Cluster:    0
      in Ketten:                      4.637

**Kein einziger der 4.637 Faelle liegt in einem vollstaendigen Cluster.** Jeder beruht auf
unvollstaendiger paarweiser Evidenz. „Transitivitaet schliessen" hiesse hier immer:
entscheiden, wo nicht gemessen wurde.

Beide Fehlerarten stecken in denselben Clustern:

    ECHTE LUECKE     „Neubau Optical Imaging Center (OIC)" dreimal, drei ueberleben
    UEBERZOGEN       „LVR-Klinikum … Moeblierung / Tragwerksplanung / Sicherheitsdienst"
                     in EINEM Cluster, verkettet ueber den Standortnamen

Blind zu schliessen heilt das erste und verschlimmert das zweite.

## Aufgabe (fuer den, der (b) angeht)

1. **Erst messen, warum die Kanten fehlen.** Bei den drei OIC-Ankuendigungen mit
   identischem Titel und identischem Kaeufer MUESSTE ein Paar entstehen. Es entsteht
   nicht. Die Seed-Wahl („die drei seltensten indizierten Woerter") ist der erste
   Verdaechtige.
2. Erst wenn die Kanten vollstaendig sind, ist Clustern sinnvoll — und dann nur ueber
   VOLLSTAENDIGE Cluster, nie ueber Ketten.
3. Die Gegenprobe ist Pflicht: nach jeder Aenderung die Groesse des groessten Clusters und
   die Zahl der verschiedenen Titel darin messen. 4.720 Knoten mit 923 Titeln ist der
   Zustand, in den man zurueckfaellt.

## Was NICHT hilft

- Union-Find ueber alle Paare (s. oben).
- Die Enthaltungsschwelle anheben: gemessen bringt 0,90 → 1,0 keinen Unterschied
  (75.462 Paare in beiden Faellen), weil die Klumpenbildner exakt 1,0 erreichen. Genau
  davor warnt der Kommentar in `dedupe.py`.
