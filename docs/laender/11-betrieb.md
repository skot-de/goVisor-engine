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

## Der Altersbericht und die Sonde

Beide laufen am Ende, beide **warnen nur** und brechen nicht ab: ein veralteter Baustein
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

Beide werden gebraucht: stehen alle Länder gleichzeitig, wandert der Bezugspunkt der Sonde
mit und sie ist blind.

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
| `GOVISOR_TAG_USD` | 6,00 $ | der Tag |
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
