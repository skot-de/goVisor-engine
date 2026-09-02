# 06 · Cross-Verdrahtung — vom Gold in die Oberfläche

> Tor 5. Fällt, wenn keine Kennzahl in Gold liegt und in der Oberfläche fehlt, und die
> Feldabdeckung je Land **nebeneinander** gemessen wurde.

## Warum dieses Kapitel das wichtigste ist

Parquet zu bauen, das niemand liest, ist derselbe Fehler wie ein Builder, den niemand
aufruft — nur eine Schicht weiter aussen. Genau das ist passiert: die 16 Gold-Tabellen aus
[Kapitel 05](05-gold-kette.md) waren gebaut, und der Export las **weiter nur DE**. Ohne
diesen zweiten Schritt wäre die ganze Arbeit stumm verpufft.

## ⚠ Die handgetippte Spaltenliste ist die dritte Form desselben Fehlers

Kapitel 05 kennt den Builder, den niemand aufruft. Dieses Kapitel kennt den Export, der nur
DE liest. Am 2026-09-01 kam die dritte Form dazu, und sie ist die leiseste: **der Export, der
seine Spalten selbst aufzählt.**

`govisor/docsignals.py` erkennt **fünfzehn** Anforderungs-Signale in den Vergabeunterlagen,
`doc_signals.parquet` trägt alle fünfzehn — und `export_doc_signals.py` schrieb **sieben**
davon ins Frontend. Dieselbe Liste stand danach ein zweites Mal im API-Typ und ein drittes
Mal im Renderer. Verloren waren:

| Signal | belegte Sätze |
|---|---:|
| `binding_until` | 5.747 |
| `penalty_pct` (Vertragsstrafe) | 4.066 |
| `site_visit` | 3.723 |
| `site_visit_mandatory` | 3.723 |
| `presentation_required` | 3.576 |
| `skonto_pct` | 393 |

**Warum es keine der bestehenden Prüfungen fand.** Die Verdrahtungssonden vergleichen, ob
eine DATEI erzeugt und gelesen wird. Diese Datei wurde erzeugt und gelesen. Der Verlust
steckte eine Ebene tiefer, in den Spalten, und dort schaut keine Sonde hin. Auch die
Länderparität greift nicht: es fehlte in allen Ländern gleich.

**Die Abhilfe ist kein weiterer Test, sondern eine Quelle.** Die Felder stehen jetzt in
[`govisor/kennzahlen.py`](../../govisor/kennzahlen.py), und der Export liest sie von dort:

```python
felder = kennzahlen.DOC_SIGNALE
spalten = ", ".join(k.quelle for k in felder)
```

`tests/test_kennzahlen.py` hält die drei Stellen zusammen: jede Parquet-Spalte muss im
Verzeichnis stehen, der API-Typ muss genau dessen Schlüssel führen, und der Renderer muss
jeden davon anzeigen. Ein neues Signal fällt damit auf, statt liegenzubleiben.

⚠ **Und jede Kennzahl nennt dort ihre Bezugsgrösse** (`markt` / `vorwert` / `profil` /
`keine`). Das ist keine Verzierung: eine Zahl ohne Vergleichswert kann nie auffällig werden
und gehört dauerhaft in die Detailebene. Wer eine Kennzahl einträgt und keinen Bezug
benennen kann, hat sie noch nicht verstanden; der Konstruktor lässt sie dann auch nicht zu.

**Das Verzeichnis ist vollständig, nicht beispielhaft.** Stand 2026-09-02 stehen dort **155
Kennzahl-Plätze über dreizehn Flächen**, also alles, was ein Nutzer sieht. Die Verteilung sagt
mehr als die Summe: 58 brauchen einen Marktwert, 39 können keinen haben und gehören dauerhaft
nach unten, 23 vergleichen gegen ein Profilfeld, das wir schon haben, und 15 warten auf eine
Historie je Nutzer, die es noch nicht gibt.

⚠ **Eine Aktivierung ist keine Kennzahl, ihre Zahlen sind es.** Am 2026-09-02 kamen sieben
Einträge dazu (Fläche `aktivierung`): die fünf Lücken-Hinweise des Tagesbriefings, die Zahl
fehlender erwarteter Unterlagen und die ungelesenen Hinweise. Die Fragen und Schalter selbst
(„Habt ihr mitgeboten?", „Stelle beobachten", die Bitten um Unterlagen) stehen bewusst NICHT
drin, sie messen nichts. Beim ersten Bauen fehlten die Zahlen trotzdem, und sie wären beim
nächsten Zählen wieder als Fund aufgetaucht.

⚠ **Alle fünf Lücken vergleichen gegen ein Profilfeld, keine gegen den Markt.** Das ist kein
Zufall: eine Lücke IST der Abstand zwischen dem, was ein Vorgang verlangt, und dem, was
hinterlegt ist. Wer eine davon auf `markt` setzt, hat sie missverstanden.

⚠ **Plätze, nicht Metriken.** Dieselbe Zahl darf auf zwei Bildschirmen stehen und dort
verschiedene Bezüge haben; gesucht wird nach Bildschirm, nicht nach Metrik. Verboten ist nur
dieselbe Kennzahl zweimal auf DEMSELBEN Bildschirm.

⚠ **Und nicht über den Namen entdoppeln.** Beim Aufbau meldete ein Abgleich, der Klammern
wegwarf, drei Doppelungen, die keine waren: „Volumen belegt (Pipeline)" gegen „(Bindung)",
„Wert (Einstiegsfenster)" gegen „(Rahmen)", „Vergaben pro Jahr" gegen „(Anbieter)". Die
Klammer ist dort die Unterscheidung. Ein blindes Aufräumen hätte echte Kennzahlen gelöscht.

**Merksatz für neue Länder wie für neue Felder:** wo eine Spaltenliste getippt wird, geht
etwas verloren. Nicht heute, aber beim nächsten Feld.

### Der Beleg gehört zur Zahl, und er war der schlimmste Fall

`evidence` trägt je Signal den Satz aus der Vergabeunterlage, auf den sich die Behauptung
stützt. Median 88 Zeichen, **9.409 von 9.788 Vorgängen mit Volltext = 96 %** (gemessen
2026-09-01), seit jeher vollständig, seit jeher unsichtbar. In einem Produkt, dessen Verkaufsargument Belegbarkeit
ist, war das die teuerste Lücke von allen.

⚠ **Und beinahe wäre sie geblieben.** Beim Aufbau des Verzeichnisses stand `evidence`
ausdrücklich NICHT drin, mit der Begründung „Belegtext, keine eigene Kennzahl". Als Kennzahl
stimmt das. Als Entscheidung war es falsch: damit hatte der Beleg **gar keinen Ort**, an dem
jemand merkt, dass er nicht ankommt. Wer etwas aus einem Verzeichnis ausschliesst, muss sagen
können, wo es stattdessen geführt wird; sonst hat er es nicht eingeordnet, sondern versteckt.

⚠ **Beim Anzeigen entstand ein Sicherheitsloch.** Damit der Beleg-Span durchkommt, musste das
`esc()` aus der Zeilendarstellung verschwinden. Seitdem escaped **jede** `rows.push`-Stelle
selbst, und das ist keine Formsache: Zertifikatsnamen und das Bindefrist-Datum kommen aus
Vergabeunterlagen, also aus Text, den jemand anderes geschrieben hat.
`tests/test_beleg.py::test_jede_zeile_escaped_selbst` prüft es, weil eine neue Zeile ohne
`esc()` im Code völlig harmlos aussieht.

### Was das Verzeichnis über den Rest sagt

Es führt seit dem 2026-09-01 auch, was **noch nicht angezeigt wird** (Fläche `geplant`, 12
Einträge aus der Übergabe „einzigartige Kennzahlen + Aktivierung"). Das ist der Zweck: eine
Kennzahl, die niemand führt, wird beim nächsten Zählen wieder als Fund entdeckt.

⚠ **Zehn der zwölf haben heute keine Datengrundlage.** `doc_checklist`, `doc_analysis`,
`doc_verworfen` und `document_duplicates` existieren als Dateien nicht; sie sind im Tageslauf
verdrahtet und entstehen erstmals in der Nacht auf den 02.09. Wer eine davon bauen will,
prüft zuerst, ob die Datei da ist. Die Zahlen im Papier stammen aus einer Probefassung.

⚠ **Zwei der fünfzehn Papier-Kennzahlen laufen bereits** und stehen deshalb nicht unter
`geplant`: die bezifferte Vertragsstrafe und die Zuschlagsgewichtung aus den Unterlagen. Der
Übergabe nach ist Letztere der stärkste Neuzugang; sie rendert seit jeher mit Balken. Ihr
fehlt keine Anzeige, ihr fehlt **Abdeckung**: am 2026-09-01 waren es 205 von 1.829 offenen
Vorgängen mit mehreren Zuschlagskriterien. Das ist der Unterschied, auf den es bei diesen Kennzahlen ankommt, und er
verschwindet, wenn man „nicht sichtbar" und „nicht gebaut" verwechselt.

## Die Werkzeuge in `scripts/export_web_leads.py`

```python
_union("lead_export", key="lead_id")   # Gold: DE + jedes weitere gold/<CC>/<table>.parquet
_union("market_opportunity", mit_land=True)   # + Land aus dem Dateipfad
_silber_union("attributes")            # Silber: Baum aus Jahrespartitionen
```

**`_union(table)`** — für Gold. Eine Datei je Land, `union_by_name`, fehlende Spalten
werden `NULL`.

**`_union(table, key=…)`** — behält je Schlüssel **eine** Zeile, DE gewinnt. Nötig, weil
gemessen drei Leads in AT **und** DE liegen (EU-Einrichtungen mit Sitz in Frankfurt, die
beide Länderfilter passieren). Ohne Entscheidung vervielfacht der nachgelagerte Join sie,
und welche Zeile gewinnt, entschied der Zufall — ein Lead trug bei einem Lauf Koordinaten
und beim nächsten keine.

**`_union(table, mit_land=True)`** — leitet das Land aus dem Dateipfad ab. Für Tabellen
**ohne** `country`-Spalte.

**`_silber_union(tabelle)`** — für Silber. Getrennt, weil Gold eine Datei je Land hat und
Silber einen Baum aus Jahrespartitionen. Länder ohne die Tabelle fallen raus statt durch:
**ein Glob ins Leere ist in DuckDB ein Laufzeitfehler, kein leeres Ergebnis.**

## ⚠ Die Falle: union_by_name kann es SCHLIMMER machen

Nicht jede Tabelle darf man einfach unionieren. Entscheidend ist der **Schlüssel**:

| Schlüssel | Beispiel | Union gefahrlos? |
|-----------|----------|------------------|
| `lead_id`, `notice_id` | `lead_lot`, `lead_criteria` | ja — Leads gehören einem Land |
| Entity/Name | `buyer_stats` | fast — s. u. |
| **fachlich, länderunabhängig** | `market_opportunity` (`cpv4`), `cpv_adjacency` | **NEIN** |

`market_opportunity` ist nach `cpv4` verschlüsselt. Im Wörterbuch des Exports gewinnt der
**letzte** Treffer — schweizerische Zahlen hätten die deutschen still ersetzt. Deshalb
`mit_land=True` und das Land im Schlüssel:

```python
_seg[(land, cpv4)] = {...}
l["marktSegment"] = seg.get((l.get("land") or "DE", (l.get("cpv") or "")[:4]))
```

**Kein Rückfall auf DE**: „in Deutschland ist dieses Segment schwach" ist für eine
Schweizer Vergabe keine Aussage, sondern eine Verwechslung — und sie wäre im Markt-Tab
nicht als solche zu erkennen. Belegt: ein CH-Lead mit `cpv4=3120` zeigte vorher die
deutschen 37 Vergaben, jetzt die schweizerischen 88.

## Aggregate, die je Land gerechnet werden müssen

Manche Auswertung darf man gar nicht zusammenlegen, egal wie man schlüsselt. „Wer vergibt
in meinem Feld?" und „wie dicht ist der Wettbewerb?" sind Fragen an **einen** Markt. Eine
DACH-Summe beantwortet keine davon und verdeckt beide.

`scripts/export_strategie.py` rechnet deshalb **einen eigenen Satz Aggregate je Land**.
Die Datei ist nach Land verschlüsselt, `/api/strategie?land=…` reicht genau einen heraus —
so bleibt die Form für das Frontend unverändert und die Nutzlast beim Client wächst nicht.

Dass es die richtige Wahl war, zeigen die Zahlen:

```
DE   DB Netz · Autobahn GmbH · Leonhard Weiss     34.152 Bau-Verträge
AT   ÖBB-Infrastruktur · ASFINAG · PORR            5.754
CH   Amt für Hochbauten · ASTRA · Implenia         2.479
```

Das Land kommt aus den Regionen des Nutzers (`nutzerLand()` in `explorerCore.js`,
NUTS-Präfix) — ein eigener Länderwähler wäre dieselbe Angabe zweimal.

⚠ **Eine Route mit `?land=` nützt nichts, wenn niemand sie so aufruft.** Beide Ansichten
(Strategie und Vergabeblick) müssen es abfragen; es gibt einen Test dafür.

## Der Wächter darf nicht an DE hängen

Ein häufiger Rest: die Existenzprüfung fragt nach der **deutschen** Datei.

```python
_LP_DA = any(pathlib.Path("data/gold").glob("*/lead_predecessor.parquet"))   # richtig
_FILL  = pathlib.Path(f"{G}/lead_region_fill.parquet")                       # falsch
```

Fällt der deutsche Bau aus, wären sonst auch die vorhandenen AT/CH-Daten abgeschaltet.
Und: `{G}/tabelle.parquet` irgendwo im Quelltext lässt den Test
`test_laenderuebergreifende_tabellen_werden_unioniert` fallen — auch im blossen Wächter.

## Was legitim DE-only bleibt

- **Dimensionstabellen** (`dim_cpv`, `dim_nuts`, `dim_plz`): ihrer Natur nach
  länderunabhängig; dass sie je Land als Datei liegen, ist ein Nebenprodukt des Bauwegs.
  Die DE-Fassung ist die vollständige. Ein Test, der sie mitzählt, erzeugt drei Fehlalarme.
  ⚠ **Ausnahme `dim_nuts`**: die AT- und CH-Namen stehen **nur** in deren eigener Datei
  (gemessen 2026-08-23: DE 462 Einträge, AT 48, CH 35, ohne Überschneidung). Diese Tabelle
  muss unioniert werden.
- **`export_landing.py`**: liest bewusst nur DE. Der Kommentar dort begründet es —
  „eine Zahl, die zwei verschiedene Qualitäten mischt, ist keine Zahl". Für AT/CH ist die
  Entitäten-Auflösung schwächer, eine gemischte Vergabestellen-Zahl auf der öffentlichen
  Startseite wäre keine bessere Zahl.

## Bekannte, gemessene Grenze: Nachschlag über den Namen

Der Vergabestellen-Profil-Nachschlag geht über den **Namen**, nicht über die Kennung.
22 Käufernamen kommen in mehr als einem Land vor („Gemeinde Bergheim" gibt es in DE und
AT; „Stadtbauamt" und „Einkauf" sind ohnehin keine Namen) und treffen gemessen
**463 von 117.241**
Leads; dort gewinnt DE.

Das ist der bessere Zustand als vorher — vorher bekamen **alle** 27.000 AT/CH-Käufer gar
kein Profil und der Renderer zeigte „zu wenig Daten", eine Aussage über die Vergabestelle,
wo nur die Datei fehlte. Aber es ist **keine saubere Auflösung**; die bräuchte einen
Schlüssel aus (Name, Land) durch die ganze Profilkette. So benennen, nicht verschweigen.

## Vor einem grossen Umbau: Determinismus prüfen

Bevor man einen Export umbaut, zweimal hintereinander laufen lassen und die Ausgaben
vergleichen. `export_strategie.py` war **nicht deterministisch** (ein Sortier-Gleichstand
bei gleichem Titel und gleicher Restlaufzeit), was jeden Vorher/Nachher-Vergleich wertlos
machte.

Der erste Vergleich zeigte 346 Abweichungen und war eine **Fehlspur**: Datenzuwachs seit
dem Nachtlauf, nicht der Umbau. Erst nachdem `contract_end` den Gleichstand entschied und
zwei Läufe bitgleich waren, liess sich belegen, dass sich keine deutsche Zahl verschoben
hatte — indem die **alte Fassung aus dem Commit** gegen die heutigen Daten lief.

**Regel:** erst prüfen, ob zwei Läufe der ALTEN Fassung identisch sind. Sonst diagnostiziert
man hinterher Gespenster.

## Was ein neues Land heute bekommt

Stand 2026-08-23, gemessen mit `pruefe_verdrahtung.py --sonde pfade`. Diese Liste ist der
ehrliche Gegenpol zum Rest des Kapitels: die **Datenkette** ist länderfähig, drei
**Produktwege** sind es nicht.

Seit dem 2026-08-23 sind auch die drei **Produktwege** länderfähig, die vorher nur
Deutschland kannten. Sie standen zum Teil in **gar keinem Lauf** — die Fehlerklasse aus
[Kapitel 05](05-gold-kette.md), eine Ebene weiter aussen:

| Weg | Vorher | Nachher |
|-----|--------|---------|
| `export_suppliers.py` → Onboarding-Firmenindex | 31.459 Firmen, **keine** rein schweizerische. PORR war drin (gewinnt auch in DE), Implenia Schweiz nicht — eine Schweizer Firma fiel bei der Anmeldung auf den manuellen Pfad. | 37.896 Firmen, alle drei Länder |
| `export_web_awards.py` → Zuschlagsphase | 379 Zuschläge, alle DE, `"land"` stand **fest** im Quelltext | 1.019 (DE 379, AT 334, CH 306) |
| `export_firma_profiles.py` → `/firma` | 23 Tage alte Datei, `nuts1 LIKE 'DE_'` verwarf AT/CH komplett | AT 2.685 / CH 84 Profile mit echter Hauptregion |

Drei Fallen steckten darin, jede eine eigene Lehre:

- **Der Deckel muss je Land gelten.** `CAP = 120 je Branche` war richtig, solange nur DE
  drin war. Mit drei Ländern hätten sie sich denselben Deckel geteilt: ein deutscher
  Nutzer sähe statt 379 nur noch 196 deutsche Zuschläge. Ein Deckel soll die Liste kurz
  halten, nicht Länder gegeneinander ausspielen.
- **Ein hartkodierter Wert ist die leiseste Sorte Fehler.** `"land": "DE"` stand mitten im
  Ausgabe-Aufbau. Selbst nachdem alle Quellen alle Länder lasen, wäre jeder
  österreichische Zuschlag als deutscher ausgegeben worden — er *sieht aus wie ein Feld*.
- **Grenzgänger brauchen eine Zusammenlegung mit Beleg.** Dieselbe Firma trägt je Land
  eine eigene Identität: ACP IT Solutions kam mit vier Einträgen, darunter `solo:id:032844a`
  und `solo:id:FN32844a` — dieselbe Firmenbuchnummer in zwei Schreibweisen. Mehrfach
  vorkommende Namen stiegen von 134 auf 868. Zusammengelegt wird nur bei **zwei** Belegen:
  gleicher Name **und** mindestens ein gemeinsames CPV-4-Feld. Gemessen an allen 868
  Fällen hatte **jeder** überlappende Felder — die Bedingung steht trotzdem im Code, damit
  der erste Fall ohne Überlappung getrennt bleibt.

Bewusst DE-only und damit **kein** Mangel: `export_landing.py` (Startseiten-Zahlen —
gemischte Qualitäten wären keine Zahl), `export_supabase.py` (Push ist ohnehin aus),
`qualitaet_bericht.py` und `gap_effects.py` (interne Berichte).

⚠ **Offen geblieben:** `firma-profiles.json` ist mit den drei Ländern auf **67 MB**
(gemessen 2026-08-23)
gewachsen und wird vom Frontend als Ganzes geparst. Das trägt heute (Cache-Grenze 256 MB),
skaliert aber nicht auf weitere Länder — dieselbe Sharding-Frage wie bei den Detail-Dateien.

## Die Abnahme dieses Tors

Feldabdeckung je Land **nebeneinander** auszählen, direkt aus `web/data/leads-*.json`:

```
Feld              DE     AT     CH
region           96%    92%   100%
lose             89%    32%    79%
zuschlag         58%    26%    79%
frist            55%    11%    44%
aufwand          30%     4%    23%
```

Jede Spalte, die für ein Land auffällig abfällt, ist **entweder** ein Verdrahtungsfehler
**oder** echte Datenlage — und man muss wissen, welches von beidem. Der Weg dahin steht in
[Kapitel 02](02-input-ausschreibungen.md): in Silber nachsehen. Trägt Silber 72 % und Gold
7 %, liegt es nicht an der Quelle.
