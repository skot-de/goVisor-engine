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

Der Leistungsort wäre die bessere Achse. Er existiert bei **28 von 8.654** dieser Leads.
Es gibt also nichts Besseres — der Wert ist als `abgeleitet` gekennzeichnet, damit die
Anzeige es sagen kann. Ein stillschweigend ergänzter Wert sieht aus wie eine Quelle.

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
