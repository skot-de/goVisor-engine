# 07 · Geo und Regionen — die Ebene sitzt nicht überall gleich

> Gehört zu Tor 5. Der teuerste Einzelfehler dieser Achse hat drei Jahre lang wie eine
> gefüllte Spalte ausgesehen.

## ⚠ Die Regel, die alles andere überlagert

**„Bundesland" sitzt nicht in jedem Land auf derselben NUTS-Stelle.**

```
DE   NUTS-1 (3 Stellen)   DE2    = Bayern
AT   NUTS-2 (4 Stellen)   AT13   = Wien        AT1  wäre „Ostösterreich" (3 Bundesländer)
CH   NUTS-3 (5 Stellen)   CH021  = Bern        CH0  wäre die GANZE Schweiz
```

Ein fester Schnitt `substr(buyer_nuts, 1, 3)` ist eine **deutsche Annahme**. Gemessen
trugen dadurch **alle 3.856** Schweizer Leads mit Region dieselbe Angabe
„Schweiz/Suisse/Svizzera" und alle österreichischen eine von drei Dritteln — als Filter
null Aussage, obwohl die Leads NUTS-3-genau vorliegen.

Die Tabelle steht an **zwei** Stellen und sie müssen übereinstimmen:

```python
govisor/gold.py            _REGION_STELLEN = {"DE": 3, "AT": 4, "CH": 5}
scripts/region_ableiten.py  REGION_STELLEN = {"DE": 3, "AT": 4, "CH": 5}
```

Laufen sie auseinander, leitet das Skript eine Ebene ab, die der Export nicht liest. Ein
Test hält sie zusammen (`test_regions_ebene_stimmt_zwischen_gold_und_ableitung_ueberein`).

**Für ein neues Land:** die Verwaltungseinheit finden, nach der ein Bieter tatsächlich
filtert, und ihre NUTS-Stelle eintragen. Nicht raten — die Namen stehen in `dim_nuts` des
Landes.

## Ableitung für Leads ohne Regionskennung

Die unterschwelligen Quellen liefern oft gar kein NUTS. `scripts/region_ableiten.py`
schliesst die Lücke ohne Modell und ohne Netz:

```bash
python3 scripts/region_ableiten.py [--probe] [--laender DE,AT,CH]
```

**Warum nicht über die Postleitzahl:** naheliegend, gemessen wertlos. Von 6.460 deutschen
Leads ohne Region hatten **38** eine Käufer-PLZ (1 %). Was sie haben, ist zu 100 % der
**Käufername**.

Zwei Wege:

1. **Gleicher Käufer** — derselbe Name trägt in einem anderen Lead eine Region → übernehmen.
2. **Ortsname** — im Käufernamen steckt ein Ort, der eindeutig zu einer Region gehört.

Gemessen DE: Weg 1 allein 32 %, Weg 2 allein 20 %, beide 29 %, gar nicht 19 % — zusammen
**83 %**.

## Der eingebaute Selbsttest — und warum er Pflicht ist

Wo **beide** Wege greifen, müssen sie dasselbe sagen. Die Widerspruchsquote steht im Lauf
und ist die einzige ehrliche Auskunft über die Verlässlichkeit; ohne sie wäre es Raten mit
Nachkommastellen.

**Widerspruch heisst Verzicht.** Wer hier eine Seite wählt, rät — und nach diesem Wert wird
gefiltert.

Beim ersten AT-Lauf: **58 % Widerspruch** (DE: 6,5 %). Ohne den Selbsttest wären 9.600
abgeleitete Regionen ausgeliefert worden, mit Freude über die hohe Ausbeute.

**Richtwert:** unter 15 % ist brauchbar, darüber gehört die Ursache gefunden.

## Ortsnamen-Fallen — jedes Land hat sein eigenes Behördendeutsch

Die Ursache der 58 % war nicht der Ansatz, sondern Vokabular:

```
46×  „stadt"      IST in Österreich ein Ortsname  →  „Magistrat der Stadt Wien" → Kärnten
 7×  „kammer"      5×  „hochbau"     5×  „strassen"
 5×  „wildbach"    4×  „steuer"      1×  „stiftung"
```

Nach Ergänzung von `_KEINE_ORTE`: **10,3 %**.

Die deutsche Liste enthielt schon dieselbe Sorte: „studentenwerk" ist ein Ort in
Schleswig-Holstein, „grafschaft" eine Gemeinde in Rheinland-Pfalz.

⚠ **Für jedes neue Land diese Liste neu füllen.** Das Behördenvokabular ist national.

Zwei weitere Regeln aus der DE-Erfahrung:

- **Wortfolgen, nicht Zeichenketten.** Eine Zwischenfassung suchte den Ortsnamen als
  Teilzeichenkette; die Widerspruchsquote stieg von 8,8 % auf 21,7 %, weil sich „senden"
  in „Wiesendendorf" findet und „ahlen" in „Zahlenwerk".
- **Der längste Treffer gewinnt.** „Stadt Neustadt am Rübenberge" traf sonst auf
  „neustadt" (Thüringen) statt auf den vollen Namen.
- **Eindeutig heisst: auch der Basisname ist eindeutig** (seit 2026-09-02). Der Riegel
  verglich VOLLE Schreibweisen und lief damit an sich selbst vorbei: die PLZ-Datei führt
  „Weilheim an der Teck" (BW), „Weilheim in Oberbayern" (BY) und ein blosses „Weilheim"
  (BW) — drei Zeichenketten, also galt „weilheim" als eindeutig. „Staatliches Bauamt
  Weilheim", das in 82362 Weilheim i.OB sitzt, bekam Baden-Württemberg. Dieselbe Klasse:
  „heidenheim", „esslingen", „ehingen", „dillingen", „koenigstein" — und ausgerechnet
  „neustadt", das der Docstring als Musterbeispiel eines ausgeschlossenen Namens nennt.
  Geprüft wird deshalb auf **Wortpräfixe**: ein Name ist nur eindeutig, wenn keine
  längere Ortsbezeichnung in einer anderen Region mit denselben Wörtern beginnt. Kosten:
  10 von 5.012 Ableitungen; Ertrag: Selbsttest-Widerspruch 8,5 % → 5,0 % (2026-09-02).

## ⚠ Die PLZ-Datei von geonames ist kein Ortsverzeichnis

Sie führt jede Postleitzahl auf — und die Deutsche Post vergibt eigene an Grosskunden.
Dort steht dann die **Firma**, wo man den Ort erwartet: „siemens", „bosch",
„a nattermann cie gmbh", „BERLIN-KÖLNISCHE VERSICHERUNGEN". Gemessen 2026-09-02:

```
DE   5.317 von 17.628 Namen sind keine Orte  (30 %, gemessen 2026-09-02)
AT       0            CH       1                     ← eine deutsche Eigenart
```

Ein Käufername, der eine solche Zeichenfolge enthält, bekäme ein erfundenes Bundesland.
Gefiltert wird gegen den geonames-**Gazetteer** (`<LAND>_gazetteer.txt`, Merkmalsklasse
P = bewohnter Ort, A = Verwaltungseinheit).

⚠ **Die Reihenfolge der beiden Riegel ist nicht beliebig.** Erst Firmen raus, dann
Namen vergleichen. Eine einzige Kölner Versicherung mit „BERLIN" im Namen macht sonst
„berlin" mehrdeutig — der Basisnamen-Riegel wirft die Hauptstadt aus dem Verzeichnis und
kostet 32 belegte Widerspruchsfunde.

⚠ **EU-weit offen:** der Gazetteer liegt bisher nur für DE. Für Länder ohne Datei bleibt
der Filter aus — vertretbar, solange die PLZ-Datei dort sauber ist (für AT/CH nachgemessen),
aber vor jedem neuen Land nachzuzählen.

## Die Gegenprobe: gegen die PLZ, nicht gegen den Ortsnamen

Dieselbe Mechanik prüft auch die Leads, die schon eine Region TRAGEN — sonst gilt ein
dastehender Wert unbesehen als belegt (s. Fallenkatalog D13).

⚠ **Der erste Zeuge war der falsche.** Die Fassung vom 2026-09-01 prüfte gegen den
ORTSNAMEN und meldete 336 Widersprüche, sichtbar im Frontend als
`regionQuelle='widersprüchlich'`. Am 2026-09-02 wurde **jeder einzelne** gegen die
Käufer-PLZ aus Silber nachgeprüft — Vollerhebung, keine Stichprobe:

```
entscheidbar (PLZ eindeutig)               274 von 336
  Region stimmt, der Ortsname war falsch   134   49 %   ← Fehlalarm
  Region wirklich falsch                   140   51 %
nicht entscheidbar                          62          ← 61 davon der BER
```

Der Marker sagte also jedem zweiten Mal etwas Falsches über einen richtigen Wert.

**Die PLZ ist der bessere Zeuge, und zwar in beide Richtungen** (gemessen 2026-09-02):

```
                 Ortsname                       Postleitzahl
prüfbar          7 % der Leads mit Region       97 %
eindeutig        95 % der Namen                 99,8 %   (AT 97,8 %, CH 99,4 %)
```

Sie kennt keine Namensvarianten, keinen Behördenzusatz und keine Umlautfaltung — die
Falle aus Kapitel 14 (`Łódź` → `['d']`) trifft sie gar nicht erst. Die verbleibenden
Mehrdeutigkeiten sind echt und keine Schwäche: 12529 liegt gleichzeitig in Schönefeld
(Brandenburg) und in Berlin, die Grenzlage des Hauptstadtflughafens. Solche PLZ melden
nichts.

**Drei Tore, damit der Marker nur meldet, was ein Fehler IST:**

1. **Gültige Regionskennung**, nicht Präfix + Länge. „DEZ"/„ATZZ" sind Extra-Regio und
   bestehen jeden Längentest (DE 9, AT 513, CH 784 Leads, 2026-09-02).
2. **Ein Standort.** Führt ein Käufer mehrere Anschriften, ist eine abweichende Region
   keine Falschangabe, sondern eine andere Niederlassung — Autobahn GmbH, BWI, DB Netz,
   BAAINBw, Deutsche Rentenversicherung Berlin-Brandenburg. DE 189 → 120 Funde.
3. **Veto des Leistungsorts.** Stützt `perf_nuts` (unabhängiger Zeuge, nicht aus der
   Käufer-NUTS abgeleitet) die Region, der die Anschrift widerspricht, ist sie keine
   Falschangabe, sondern eine Aussage über den Auftrag: die AOK PLUS sitzt in Erfurt und
   schreibt für Sachsen aus. DE 120 → 80 Funde.
   ⚠ Nur als Veto, nie als Kronzeuge: `perf_nuts` ist bei DE 33 %, AT 10 % gefüllt.

Stand nach der Korrektur (2026-09-02, `--probe`):

```
        prüfbar   Widersprüche   vorher (Ortsname)
DE       81.611             80   336
AT        6.621             85    34   ← andere Basis: prüfbar war 1.362
CH        7.191             30    43   ← prüfbar war 4.841
```

## Die 80 deutschen Funde: durchgegangen und korrigiert (2026-09-02)

Der Marker sagt, DASS Anschrift und Regionsangabe auseinanderlaufen. **Welche Seite recht
hat, kann er nicht sagen** — dafür braucht es einen Blick auf den Fall. Alle 80 sind
einzeln durchgegangen; der entscheidende Zeuge war meist der Käufer selbst, weil dieselbe
Behörde in Silber hundertfach vorkommt:

```
AOK PLUS      eigene Angabe 899× Thüringen gegen 145× Sachsen, Anschrift Erfurt
BAAINBw       eigene Angabe 3.863× Rheinland-Pfalz, Dienstsitz Koblenz
Buxtehude     eigene Angabe 114× Niedersachsen gegen 1× Mecklenburg-Vorpommern
```

**Wo eine Behörde ihre Region hundertfach gleich angibt, ist die Ausreisserzeile der
Fehler.** Ergebnis: 37 Fälle korrigiert, **1 bestätigt** — die BKK VerbundPlus sitzt in
Biberach (DE1) und führt München nur als Zweitanschrift, ihre Angabe stimmt.

Das Urteil steht in `curated/DE_region_korrektur.csv`, versioniert im Repo, mit Beleg je
Zeile — dieselbe Bauart wie `DE_entity_aliases.csv`: **von Hand geprüft, kein
Namensstamm-Automatismus.** Schlüssel ist Käufername **und** PLZ; zieht eine Behörde um,
greift die Zeile nicht mehr, und das ist gewollt. Ein Test hält tote Zeilen fest.

⚠ `region_neu == region_alt` heisst **geprüft und richtig** — dann schweigt der Marker,
statt weiter zu melden. Ohne diese Möglichkeit hätte eine Kuratierung nur einen Ausgang,
und der bestätigte Fall bliebe für immer rot.

⚠ **Die Korrektur greift VOR den drei Toren.** Eine kuratierte Zeile ist eine Aussage über
den Fall, kein Verdacht — sie muss auch dort wirken, wo ein Tor den Verdacht gar nicht
erst aufkommen lässt. Deshalb sind es **93 korrigierte Leads, nicht 80**: bei der AOK PLUS
deckte das Leistungsort-Veto 13 weitere Leads mit derselben falschen Angabe.

⚠ **Korrigiert werden muss die KENNUNG, nicht nur das Label.** Der Regionsfilter im
Explorer prüft `l.nuts.startsWith(code)` (`ORTE` in `web/lib/explorerCore.js` kennt nur
die 16 dreistelligen Kennungen). Wer nur `region` setzt, repariert die Anzeige und lässt
den Filter falsch — der Lead sähe richtig aus und stünde weiter im falschen Bundesland.

⚠ **Und der Marker selbst wird bis heute nirgends angezeigt.** `regionQuelle` steht in
`web/data/leads-*.json` (150 × `widerspruechlich`, gemessen 2026-09-02), aber **kein
einziger Treffer in `web/`** liest das Feld. Der sichtbare Teil dieser Kette ist allein
der Wert von `region` — deshalb korrigiert die Kuratierung ihn und verlässt sich nicht
auf ein Etikett. Die Anzeige des Etiketts ist offen.

⚠ **Was in AT übrig bleibt, ist eine ehrliche Grenze.** 75 der 85 Funde sind zwei
Käufer — Flughafen Wien AG (Sitz Schwechat/AT12, meldet AT13) und OMV Austria E&P. Eine
Organisation mit EINER Anschrift, deren Sitz in einer anderen Region liegt als die, die
sie angibt, ist aus einem einzelnen Satz nicht von einem Tippfehler zu unterscheiden.
In DE trägt diese Klasse 3 % der Funde, in AT 80 %.

## Verwaltungsnamen an geonames knüpfen

geonames kennt keine NUTS, nur Verwaltungsnamen. Für AT und CH kommt die Zuordnung aus
`dim_nuts` des Landes und wird über den **Namen** verknüpft.

⚠ **Die Vorsilbe steht auf der geonames-Seite.** `dim_nuts` sagt „Bern / Berne", geonames
sagt „**Canton de** Berne", „**Kanton** Aargau". Der erste Versuch schnitt auf der falschen
Seite ab und erkannte **646 von 4.520** Schweizer Zeilen — die vier grössten Kantone
fielen komplett aus. Nach der Korrektur: 3.939 eindeutige Ortsnamen.

Ebenso: die Schweizer Namen sind **mehrsprachig** („Valais / Wallis"). Jeder Namensteil
wird einzeln eingehängt.

⚠ geonames führt die deutschen Länder auch auf **Englisch** („Bavaria", „Lower Saxony").
Diese Zeilen sind Dubletten und werden übersprungen, nicht übersetzt — sonst zählte man
denselben Ort zweimal und hielte ihn für mehrdeutig.

## Ergebnis in Zahlen

```
Regionsabdeckung   DE  96 %      AT  37 % → 92 %      CH  79 % → 100 %
```

## ⚠ Ehrlich dazusagen: der Sitz ist nicht der Leistungsort

**88 % der österreichischen Ableitungen zeigen auf Wien**, amtlich sind es 58 %. Der Grund
ist vollständig geklärt: **ÖBB und ASFINAG stellen 88 % davon** — beide mit Sitz in Wien,
beide österreichweit tätig. Dieselbe Eigenschaft, die DB Netz in Deutschland hat
(17 Bundesländer).

Der Leistungsort wäre die bessere Achse. Er existiert bei **19 von 8.383** dieser Leads
(gemessen 2026-08-23 NACH der Kanton-Umstellung; davor 28 von 8.654 — die Zahl wandert
mit dem Bestand, die Aussage nicht).
Es gibt also nichts Besseres — der Wert ist als `abgeleitet` gekennzeichnet, damit die
Anzeige es sagen kann. Ein stillschweigend ergänzter Wert sieht aus wie eine Quelle.

## ⚠ Trägt die Quelle überhaupt NUTS — oder nur nationale Kürzel?

Diese Frage klingt nach einer Formalie und war der teuerste Einzelfund des kritischen
Durchgangs am 2026-08-23.

simap.ch liefert als Leistungsort einen **Kantonscode** (`ZH`, `VD`, `BE`), und der stand
roh in `performance_nuts`. Gemessen, was das kostete:

```
 4.850 Schweizer Zuschläge trugen ein zweistelliges Kürzel  → aus JEDER Regionsanzeige raus
19.572 trugen „CH0"                                         → NUTS-1, das ganze Land
   933 trugen ein echtes fünfstelliges NUTS
```

Die Folgen zogen sich durch das ganze Produkt: die Zuschlagsphase zeigte bei **306 von 306**
Schweizer Zuschlägen keine Region, der Lieferantenindex kannte **6** Schweizer Regionen.

⚠ **Und ein falsches Kürzel ist gefährlicher als eine Lücke:** `BE` ist in der Schweiz
**Bern**, im NUTS-Raum aber **Belgien**. Ein Verbraucher, der auf das Präfix schaut, ordnet
den Kanton Bern dem falschen Land zu.

**Die Lehre: das gehört an die Quelle, nicht in jeden Verbraucher.** Die Zuordnung sitzt
jetzt im Parser (`govisor/simap.py`, `_KANTON_NUTS`), also vor Silber — damit bekommt jede
nachgelagerte Auswertung sauberes NUTS, ohne davon zu wissen. Nach der Korrektur: 933 →
**20.459** Sätze mit fünfstelligem NUTS.

Zwei Regeln daraus für jedes neue Land:

1. **Die Zuordnung muss vollständig sein und geprüft werden.** 26 Kantone auf genau die 26
   fünfstelligen CH-NUTS aus `dim_nuts`, ohne Rest auf beiden Seiten — ein Test hält das
   fest. Ein getippter Code, den es nicht gibt, fällt so beim Bauen auf und nicht in der
   Anzeige.
2. **Unbekanntes bleibt stehen, nicht leer.** Wer ein unbekanntes Kürzel auf `None` abbildet,
   verliert die Angabe still. Ein unbekanntes Kürzel ist eine Auskunft über die Quelle.

## Zwei Achsen, die man nicht verwechseln darf

- **Käufersitz** (`buyer_nuts`) — fein (PLZ-genau), aber bei bundesweiten Käufern falsch.
- **Leistungsort** (`perf_nuts`) — richtig, aber grob und oft leer.

`region_kpi` aggregiert bewusst über den **Leistungsort**: der Käufersitz führt bei
bundesweiten Käufern in die falsche Region, und DÖE-Leads kämen sonst gar nicht rein
(`buyer_nuts` dort 0 % gefüllt, `perf_nuts` 77 %).

Der Lead selbst zeigt den **Käufersitz**. Die Inkonsistenz ist bewusst; wer sie ändert,
ändert sie für alle Länder.

## Bundesweite Vergaben

`RealizedLocation.Address.Region = anyw*` heisst „an keinen Ort gebunden". 4.144 deutsche
Leads fielen dadurch aus **jeder** Umkreis- und Regionssuche, obwohl sie zu jedem Standort
passen. Die Regel liegt zentral in `geo.nationwide_clause()` — `geo.search()` und
`app/radius_suche.py` bauten ihr SQL getrennt und hatten den Fehler **doppelt**.

Konvention: bei gesetztem Radius heisst `dist_km IS NULL` = **bundesweit**, nicht
„unbekannt". Sortiert an den Rand des Umkreises: hinter alle echten Nahtreffer, aber vor
dem Abschneiden durch `limit`. München 25 km: 4.987 → 9.071 Leads.

**Für ein neues Land: das Gegenstück dieser Markierung finden.**

## PLZ und Koordinaten

`dim_plz` (GeoNames-Zentroide) speist die echte Umkreissuche.

⚠ **AT und CH haben BEIDE vierstellige PLZ und kollidieren** (1010 = Wien AT / Lausanne
CH). `plz-geo.json` ist deshalb nach Land verschachtelt: `{DE:{…}, AT:{…}, CH:{…}}`.

⚠ Der Stadtindex `_cities` (`build_city_index.py`) wird von `export_web_leads.py`
überschrieben, wenn man nicht aufpasst — die Datei trägt beides.
