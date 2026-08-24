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
- **`pruefe_verdrahtung.py`** — alle Gold-Dateien, relativ zum Lauf ihres Landes. Merkt,
  wenn **ein** Schritt fehlt.

Beide werden gebraucht: stehen alle Länder gleichzeitig, wandert der Bezugspunkt der Sonde
mit und sie ist blind.

## Geldwache

Alles, was ein Modell kostet, läuft durch `llm.chat()` — **die Bremse sitzt dort, nicht im
Aufrufer**. Vier Regeln (Reserve, Limit, Takt, Protokoll) stehen in der Auto-Memory
`govisor-geldwache`.

Für ein neues Land relevant, sobald man LLM-gestützte Schritte einschaltet
(Nachfolge-Adjudikation, Dokumentanalyse). Ein Voll-Lauf über 105.000 Nachfolgen kostete
**$2.01** — das ist die Grössenordnung, mit der man rechnen darf, nicht mehr.

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
