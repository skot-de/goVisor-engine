# 11 · Betrieb — Nachtlauf, Sperren, Kosten

> Ein Land, das gebaut ist und nicht täglich läuft, ist nicht fertig.

## Der Tageslauf

`scripts/daily_leads.sh` ist die einzige Stelle, an der die Kette vollständig steht. Wer
einen Schritt baut und ihn hier nicht einhängt, hat ihn nicht fertig gebaut — das ist die
Fehlerklasse aus [Kapitel 05](05-gold-kette.md), eine Ebene höher.

Grobe Reihenfolge:

```
Ingest (TED, DÖE, atverg, simap, Portale)
  → Silber
  → Dubletten-Firewall + Anreicherung (DE/AT/CH)
  → Kategorie-Wasserfall            liest notice_duplicates, schreibt lead_kategorie
  → AT/CH-Gold (build_dach_gold.py)
  → DE-Gold mit heutigem Stichtag
  → Bundesländer ableiten           region_ableiten.py
  → Frontend-Daten (web/data)
  → Marktpuls, Strategie, Regionen, Startseite
  → Ertragsbericht
  → Altersbericht + Verdrahtungsprüfung + Bibel-Prüfung
```

Sonntags läuft die volle Historie der Firewall (`--ab-jahr 2004`), sonst ein rollendes
Fenster (`--fenster-tage 190`).

**Für ein neues Land:** jeden Schritt durchgehen und fragen, ob er das Land kennt. Die
meisten nehmen `--laender` oder `--country`; einige nicht, und die sind der Punkt.

## Die Uhr — ein Lauf, der nicht endet, liefert nichts

Der Tageslauf hat **zwei** Zeitgrenzen, und die zweite ist die wichtigere:

| Grösse | Vorgabe | Bedeutung |
|--------|---------|-----------|
| `GOVISOR_GRENZE_GESAMT` | 28.800 s (8 h) | ab hier bricht der Lauf ab — `exit 75` (EX_TEMPFAIL), nicht Fehler |
| `GOVISOR_ERNTE_KERN` | 3.600 s (60 min) | **reserviert** für Export, Wächter und Ertragsbericht |

`nur_mit_zeit()` steht vor sieben aufschiebbaren Schritten. Bleibt weniger als der
Erntekern übrig, meldet der Schritt „⏭ aufgeschoben" und der Lauf geht weiter — **kein
Abbruch**. Die Regel dahinter:

> **Ein aufgeschobener Schritt kostet einen Tag Frische. Ein abgeschnittener Lauf kostet
> den Tag komplett.**

Wer oben abschneidet, verliert unten das Produkt: Bundesländer, Frontend-Export,
Namenswörter und Ertragsbericht stehen am **Ende** der Kette. Die 60 Minuten sind gemessen,
nicht geschätzt — über neun Läufe (02.09.–09.09.) brauchte der Pflichtteil
3 · 4 · 4 · 5 · 7 · 21 · 24 · 26 · 26 min, also gut das Doppelte des schlimmsten Falls.

⚠ **`exit 75` statt `exit 1`.** „Nicht gelaufen, später erneut versuchen" ist etwas anderes
als „kaputt". Ein Lauf, der am Zeitdeckel endet, darf den Betreiber nicht so alarmieren wie
einer, der an einer Ausnahme stirbt.

**Der Anlass:** ein Lauf am 2026-09-09 lief 494 Minuten und wurde abgebrochen — ohne
Frontend-Export, ohne Wächter, ohne Bericht. Mit Deckel und Erntekern liegen die Läufe
seitdem bei 59 bis 83 Minuten.

## Die Maschine muss wach bleiben

⚠ **Der Mac schläft mitten im Nachtlauf ein, und nichts daran sieht nach einem Fehler aus.**
Gemessen in der Nacht zum 2026-09-10: von 405 Minuten Laufzeit schlief die Maschine **344**.
Die Schritte liefen alle, sie liefen nur nicht.

```bash
caffeinate -i -w $$ &     # haelt wach, solange der Lauf lebt; stirbt mit ihm
```

`-i` verhindert nur den **Leerlauf**-Schlaf, nicht den Deckel-zu-Schlaf, und `-w $$` bindet
die Lebensdauer an den Lauf: kein verwaister Prozess, der die Maschine tagelang wach hält.

Wer wissen will, ob es hilft — `scripts/maschine_mitschreiben.sh` schreibt alle 30 Sekunden
Last, Swap, freien Speicher und Pageins nach `data/logs/maschine-<datum>.tsv`. Ohne diese
Mitschrift war „der Lauf war langsam" nicht von „die Maschine schlief" zu unterscheiden.

## ⛔ Laufkollisionen prüfen — vor JEDEM schreibenden Schritt

```bash
scripts/laeuft_was.sh && python3 -m govisor.docfetch_...
```

Unmittelbar davor, nicht „ich habe vorhin geschaut". Der Tageslauf schützt sich per Sperre;
**Aufrufe von Hand tun das nicht**, und genau die sind der Grund.

Warum es zählt: `index-docs --neu-aufbauen` liest stundenlang denselben Baum
`data/docs/DE`, in den ein Abruf schreibt. Neue ZIPs mitten im Neuaufbau werden übersehen
oder halb gelesen. Am 2026-08-15 lief so ein Neuaufbau 9,5 h, war durch, und **startete am
selben Abend erneut**.

⚠ **Zwei Fallen im Prüfskript selbst**, beide dort dokumentiert:

- `ps aux` schneidet ohne Terminal bei 80 Zeichen ab — das Wort „govisor" fällt weg.
- `ps … | grep -q` liefert mit `set -o pipefail` **Exit 141 bei Erfolg**.

Beide Male lautet die Fehlmeldung „Bahn frei".

## Die Sperre selbst nehmen

Wenn Arbeiter laufen und man trotzdem schreiben muss, nimmt man die Sperre, die sie
respektieren — statt sie zu umgehen:

```bash
LOCK="data/.daily_leads.lock"
mkdir "$LOCK" && echo $$ > "$LOCK/pid"     # atomar
# … Arbeit …
rm -rf "$LOCK"
```

Die Dokument- und Analyse-Arbeiter halten an ihrer nächsten Schleife an. **Immer wieder
freigeben** — eine verwaiste Sperre blockiert den Nachtlauf.

## launchd-Fallen

Zwei Dinge scheitern **stumm**:

1. **System-Python hat kein duckdb.** Der Lauf braucht den expliziten Interpreter:
   `/Library/Frameworks/Python.framework/Versions/3.14/bin/python3`, mit Rückfall auf
   `python3`.
2. **Kein Schreibrecht ausserhalb des Projekts.**

Dazu die klassische Falle: ein Skript, das `govisor` importiert, ohne `sys.path` zu setzen.
Unter launchd fehlt das Arbeitsverzeichnis. Genau so fiel `export_web_awards.py` aus.

## Die beiden Dauerarbeiter

Neben dem Tageslauf laufen **zwei** launchd-Dienste rund um die Uhr:

| Dienst | Skript | Was |
|--------|--------|-----|
| `eu.govisor.dokumente` | `scripts/dokumente_arbeiter.sh` | holt Vergabeunterlagen |
| `eu.govisor.analyse` | `scripts/analyse_arbeiter.sh` | analysiert, was geholt wurde |

⚠ **Seit dem 2026-08-18 holt der Tageslauf keine Unterlagen mehr** („das macht der
Dauerarbeiter"). Damit ist jede Prüfung, die nur `daily_leads.sh` liest, auf einem Auge
blind — die eigentliche Arbeit steht woanders. Genau so blieb `rueckstau.py` vier Wochen
lang auf `data/gold/DE` festgenagelt: Adressen aus LU, AT und CH kommen in deutschen Leads
nicht vor, ihr Rückstau stand dauerhaft auf 0, und **ein leerer Rückstau sieht aus wie
erledigte Arbeit**. Sonde 3 liest deshalb heute auch die Arbeiter, nicht nur den Tageslauf
(Fallen G28 und G31 in [Kapitel 12](12-fallenkatalog.md)).

### Wer als Nächstes drankommt

`scripts/waehle_abrufer.sh` wählt je Runde drei Abrufer: **zwei** aus dem Feld mit
nennenswertem Rückstau (`ABRUF_MINDEST`, Vorgabe 50) und **einen**, der über alle rotiert,
bei denen sich eine Stunde noch lohnt (`ABRUF_MINDEST_KLEIN`, Vorgabe 10) — abzüglich der
beiden schon gewählten.

⚠ **Die Rotation stand still, und nichts zeigte es.** Bei drei Kandidaten in der Liste ist
`2 + (RUNDE-1) % (3-2)` **immer 2**: der dritte Platz bekam über Wochen denselben Abrufer.
Eine Rotation, die nicht rotiert, sieht in jeder einzelnen Runde völlig richtig aus — sie
fällt nur auf, wenn man mehrere Runden nebeneinanderlegt.

## Die neun Wächter am Ende des Laufs

Alle laufen am Ende, alle **warnen nur** und brechen nicht ab: ein veralteter Baustein
ist ein Grund hinzusehen, keiner den Lauf wegzuwerfen.

- **Altersbericht** — handgepflegte Liste von sechs Eckpfeilern, absolute Frische. Merkt,
  wenn der **ganze** Lauf steht.
- **`pruefe_bibel.py`** — prüft die Anleitung selbst: Zahlen ohne Datum, Behauptungen
  gegen die Live-Daten, Doppelpflege mit `CLAUDE.md`, und ob ein Kapitel stillstand,
  während der Code darunter sich bewegte. Ebenfalls Warnung, kein Abbruch.
  `--stand` zeigt, wie alt jedes Kapitel ist — **aus git**, nicht getippt: ein
  handgeschriebenes „Stand: …" verrottet in dem Moment, in dem jemand das Kapitel ändert
  und die Zeile vergisst.
  ⚠ **Der Nachlauf hat eine Frist.** Unter 30 Tagen ist er ein Anstoss zum Hinsehen,
  darüber ein Fehlschlag. Grund: eine Warnung ohne Frist ist folgenlos — man kann sie
  beliebig lange ignorieren, und genau das passiert mit jeder Meldung, die nie eskaliert.
  Kürzer als 30 Tage ginge nicht, weil `daily_leads.sh` und `sources.py` sich ständig
  ändern; dann wäre aus dem täglichen Rauschen ein täglicher Fehlschlag geworden.
- **`pruefe_verdrahtung.py`** — alle Gold-Dateien, relativ zum Lauf ihres Landes. Merkt,
  wenn **ein** Schritt fehlt.
- **`pruefe_gold_integritaet.py`** — jeder Fremdschlüssel in Gold muss auflösen, in **jedem**
  Land. Merkt, wenn eine Eltern-Tabelle ersetzt wurde, während die Kind-Tabelle stehenblieb.
  ⚠ Die Prüfung selbst (`verify.gold_integrity`) ist alt; **aufgerufen** hat sie der
  Tageslauf bis zum 2026-09-02 nie. Sie hing an `python -m govisor.cli verify`, und der
  prüft davor jeden Monat seit 2004 gegen die TED-Search-API — ein Netzlauf, den niemand
  täglich startet. Die Integrität allein kostet über DE+AT+CH zusammen **1,3 s** (gemessen
  2026-09-02); teuer war ausschliesslich das Beiwerk. Aufgefallen ist die Lücke an
  28 Waisen im Dublettenwall (AT), die mindestens einen Tag unbemerkt dastanden.
  **Die Länder kommen von der Platte**, nicht aus einer Liste — sonst prüft der Wächter
  ein viertes Land stillschweigend nicht.

- **`pruefe_laender_tabellen.py`** — trägt **jede** Wertetabelle jedes aktive Land?
  `_REGION_STELLEN`, `_PLZ_STELLEN`, `locales`, `LAND_LABEL` … Eine zentrale Länderliste
  kann `DE=5, AT=4` nicht erfinden, aber sie kann einen fehlenden Eintrag laut machen
  ([Kapitel 15](15-eintragungsliste.md)).
- **`pruefe_abdeckung.py`** — kommt überhaupt noch etwas an, und ist die Geschichte
  vollzählig? Drei Stufen: abgeschlossene Monate, laufender Monat als Fenstersumme,
  und eingelesene Bronze-Monate gegen die Pakete im Cache
  ([Kapitel 02](02-input-ausschreibungen.md)).
- **`pruefe_nuts_vorgabe.py`** — findet eine Regionskennung, die in Wahrheit ein
  Vorgabewert ist. Anlass: DÖE trug über den gesamten Bestand **genau einen** NUTS-Wert
  (`DEA22`, Bonn) auf 33.966 Käuferzeilen in 393 verschiedenen Orten.
- **`pruefe_endgueltige.py`** — hält ein endgültiges Urteil noch? Wer einen Abrufer als
  „verschlossen" abhakt, darf das nicht auf ewig glauben; von elf handgeprüften
  Dokument-Abrufern hielten neun Urteile nicht.
- **`pruefe_sondierung.py`** + **`pruefe_sondierungszahlen.py`** — halten die
  Sondierungs-Unterlagen fest, dass ein *angesehenes* Land kein *angebundenes* ist, und
  rechnen jeden Prozentsatz darin aus den Messdaten nach. Eine Zahl in einem Dokument
  altert schneller als der Code darunter.

Alle werden gebraucht, und keiner ersetzt einen anderen: stehen alle Länder gleichzeitig,
wandert der Bezugspunkt der Verdrahtungs-Sonde mit und sie ist blind — während der
Altersbericht genau dann anschlägt.

## Geldwache

Alles, was ein Modell kostet, läuft durch `llm.chat()` — **die Bremse sitzt dort, nicht im
Aufrufer**. Wer daran vorbeipostet, umgeht sie vollständig; `scripts/succession_llm.py` tat
das bis zum 2026-08-24 und war dabei monatelang stumm defekt (fest eingetragenes Modell,
das es nicht mehr gab, jeder Aufruf ein HTTP 404, vom `except` geschluckt).

Die Einzelheiten stehen in [`docs/modellwahl-und-anbieterboden.md`](../modellwahl-und-anbieterboden.md).
Hier nur, was man für den Betrieb wissen muss.

### Die Grenzen

| Grenze | Vorgabe | wogegen |
|--------|---------|---------|
| `GOVISOR_RESERVE_USD` | 1,00 $ | Guthaben ganz leerlaufen |
| `GOVISOR_LIMIT_USD` | 5,00 $ | ein einzelner Lauf |
| `GOVISOR_TAG_USD` | 5,00 $ | der Tag (angehoben von 2,00 auf 5,00 am 2026-09-14) |
| `GOVISOR_UPLOAD_TAG_USD` | 2,00 $ | **eigener Topf.** Ein Upload wartet nicht: der Nutzer steht davor. Deshalb steht `upload` in `llm.VORRANG` und geht am Tagesdeckel vorbei — aber nicht an allem |
| `GOVISOR_SCHONUNG_USD` | 0,50 $ | dass die Produktion dem Prüfstand nichts übrig lässt |
| `OR_MAX_TOKENS` | 56.000 | davonlaufende Ausgabe |
| `OR_FRIST` | 600 s | hängende Aufrufe |

**Die Schonung ist die Antwort auf einen realen Zusammenstoss.** Ein Topf, der nur eine
Obergrenze hat, ist begrenzt und nicht geschützt: Analyse-Arbeiter und Prüfstand teilten
sich Reserve und Tagesdeckel, und der Arbeiter läuft alle 30 Sekunden gegen einen
Prüfstand, der einmal nachts läuft. Wer zuerst da ist, nimmt alles. Für alle Zwecke ausser
`pruefstand`/`bench` liegen die Grenzen deshalb um die Schonung straffer.

### ⚠ Jede Zahl, die aus dem Kontostand abgeleitet wird, überlebt keine Aufladung

Am 2026-08-24 dreimal dieselbe Klasse gefunden. Das Tagesbuch rechnete
`max(0, Stand_vom_Tagesbeginn − Stand_jetzt)`; nach einer Aufladung steigt der Stand über
den Startwert, die Differenz wird negativ und `max` macht daraus **null**. Es meldete
0,00 $, während das Kostenbuch am selben Tag 36,64 $ auswies — der Deckel hätte an genau
dem Tag nicht gegriffen, an dem aufgeladen wurde.

Grundlage ist jetzt OpenRouters `total_usage`: die Zahl steigt nur und kennt keine
Aufladung. Dasselbe gilt für `kostenbericht.py --abgleich`.

### Das Kostenbuch

`govisor/kostenbuch.py` schreibt **jeden** Aufruf mit — Preis aus `usage.cost` der Antwort,
Endpunkt, Zweck, Vorgangs-ID. Es kostet nichts (die Zahl steht ohnehin in der Antwort) und
es bremst nicht; die Bremse bleibt die Geldwache.

Warum es unentbehrlich ist, zeigt der teuerste Fund des 2026-08-24: die Endung `:floor`
soll den günstigsten Endpunkt erzwingen. **Sie ist eine Bitte, keine Garantie.** Über 311
Aufrufe gemessen, alle mit `:floor` gesendet:

```
304×  Standard 0,300/2,500  über „Google" (Vertex)
  5×  Flex     0,150/1,250  über „Google AI Studio"
```

Bezahlt wurden 2,45 $ statt 1,27 $ — 48 % zu viel, bei einem Kontostand, der völlig
plausibel fiel. Erzwungen wird der Bodenpreis erst durch `max_price`, und der Deckel wird
aus dem Modell selbst abgeleitet (`llm.bodendeckel()`), nie fest eingetragen.

⚠ **Das Buch kann nie vollständig sein.** Ein Client-Timeout wird oben abgerechnet, ohne
dass wir die Antwort sehen. Deshalb weist es seine eigene Lücke aus:

```bash
scripts/kostenbericht.py --abgleich      # Buch gegen OpenRouters total_usage
scripts/kostenbericht.py --nach zweck    # wofür ging das Geld
```

### Rückstau in Etappen, mit Schranke dazwischen

```bash
scripts/rueckstau_etappen.sh             # Etappe → Schranke → Etappe
scripts/qualitaetsschranke.py --verlauf  # alle Etappen nebeneinander
```

Die Schranke misst nach jeder Etappe sieben Dinge gegen die Voretappe: Tarifanteil,
Buchabgleich, Ausbeute, Verwerfungsquote, Müll, Stückkosten, Testsuite. Bei rot **hält der
Abbau an**, statt zu warnen — er läuft stundenlang unbeaufsichtigt, und eine
Verschlechterung, die nur ins Log schreibt, produziert bis zum nächsten Hinsehen tausende
schlechter Analysen.

⚠ **PARALLEL 8, nicht 40.** Die Geldwache prüft in Abständen; bei 40 gleichzeitigen
Anfragen sind im Moment des Abbruchs bis zu 40 unterwegs. Gemessen über drei Etappen am
2026-08-24: Stopp bei 10,16 / 10,11 / 10,18 $ gegen ein 10-$-Ziel.

⚠ **Eine Etappe, die nichts verbraucht, heisst „nichts mehr zu tun".** Als der Rückstau
abgearbeitet war, drehte die Schleife 37 Leerrunden in wenigen Minuten — Analyse startet,
findet nichts, endet; Schranke misst null neue Aufrufe und meldet folgerichtig grün. Ein
Lauf, der nichts tut, sieht von aussen aus wie einer, der alles richtig macht. Geprüft wird
deshalb am Kontostand.

### Grössenordnungen

Gemessen am 2026-08-24, zum Flex-Tarif und mit acht parallelen Fäden:

```
Dokumentanalyse     0,024 $ je Vergabe
Nachfolge-Adjudikation   2,01 $ für einen Voll-Lauf über 105.000 Nachfolgen (2026-08)
Modellkandidat prüfen    0,04 $ je Absage (Vorprüfung über drei Vergaben)
```

Für ein neues Land relevant, sobald LLM-gestützte Schritte eingeschaltet werden. Die
Dokumentanalyse setzt Volltext voraus — AT und CH haben davon nichts
([Kapitel 03](03-input-dokumente.md)), also fällt dieser Posten dort heute weg.

### Modellwahl

Welches Modell gefahren wird, entscheidet nicht mehr das Guthaben, sondern ein täglicher
Wächter und ein Prüfstand, der Kandidaten an **denselben** Vergaben misst wie den
Amtierenden. Qualität zuerst, dann der Preis; ein eklatanter Preisunterschied darf einen
kleinen Qualitätsverlust aufwiegen, Ungenauigkeit dagegen nie.

```bash
scripts/modellwaechter.py --pruefen      # täglich, kostenlos
scripts/modellpruefung.py --trocken      # was würde ein Lauf kosten?
scripts/modellpruefung.py --stand        # Warteschlange und Urteile
```

⚠ Der Prüfsatz stammt aus `data/docs/<LAND>/doc_text.parquet` und steht per Vorgabe auf DE
— **eine Datenlage, keine Bequemlichkeit**: ohne Volltext gibt es nichts, woran sich zwei
Modelle unterscheiden könnten.

## Zwei Sitzungen parallel

Steht in `CLAUDE.md` und ist Betriebsrealität:

- **⛔ NIE `git commit -a` oder `git add -A`.** Immer die eigenen Pfade einzeln nennen.
  Am 2026-08-22 zweimal passiert: Landing-Kacheln landeten in einem Commit über
  OpenRouter-Stapelverarbeitung.
- Eine Sitzung besitzt `web/`, die andere `govisor/` und `scripts/`.
- Eine **rote Suite ist mehrdeutig** — im Zweifel die fremde Datei wegstashen und den
  Test allein laufen lassen.
- Den Dev-Server auf Port 3000 fährt nur eine Sitzung; für die zweite steht
  `govisor-web-3100` in `.claude/launch.json`.

## Umgebungsschalter

Nicht Code, sondern Betrieb — und sie liegen beim Betreiber:

```
LAUNCH_LIVE        Baustellen-Sperre aufheben
PREVIEW_KEY        Vorschau-Zugang (fail-closed: ohne Wert kein Bypass)
ZUGANG_PFAD        zweiter Weg hinter den Vorhang
DATA_BASE_URL      Objektspeicher statt lokaler Platte
CRON_SECRET        geplante Läufe absichern
PAYWALL_ENFORCED   Free/Pro-Regeln scharf schalten
```

⚠ **Fail-closed ist Absicht.** Ist `PREVIEW_KEY` leer, gibt es den Bypass nicht. Wer beim
Debuggen einen lokalen Wert setzt, schreibt dazu, dass er nur lokal gilt.
