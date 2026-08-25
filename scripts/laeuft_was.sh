#!/bin/bash
# ============================================================================
# goVisor — „Störe ich gerade jemanden?"
#
# VOR jedem Schritt aufrufen, der schreibt: Dokument-Abrufe, Gold-Neubau, Silber-Ingest,
# Migrationsskripte. Gibt 0 zurück, wenn die Bahn frei ist, sonst 1.
#
# WARUM ES DAS GIBT. Am 2026-08-15 lief `index-docs --neu-aufbauen` neuneinhalb Stunden über
# `data/docs/DE` — genau den Baum, in den ein Unterlagen-Abruf schreibt. Neue ZIPs mitten in
# einen Neuaufbau zu legen heisst im besten Fall, dass sie übersehen werden, im schlechteren,
# dass eine halb geschriebene Datei eingelesen wird. Am selben Abend startete ein ZWEITER
# solcher Lauf, nachdem der erste durch war — „ich habe vorhin geprüft" ist also keine
# Auskunft. Es zählt nur der Blick unmittelbar davor.
#
# Der Tageslauf schützt sich selbst per Lock. Ad-hoc-Aufrufe von Hand tun das NICHT — sie
# sind der eigentliche Grund für dieses Skript.
#
# Aufruf:  scripts/laeuft_was.sh && python3 -m govisor.docfetch_...
# ============================================================================
set -uo pipefail
# Vom eigenen Ort aus, nicht von einem eingetippten Pfad. Der stand hier fest verdrahtet —
# als einziges Skript im Projekt. Ein verschobenes Verzeichnis haette die Pruefung stumm
# ins falsche Zielverzeichnis schauen lassen, und sie haette „Bahn frei" gemeldet.
cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"
frei=0

echo "── Tageslauf-Lock ──"
if [ -d data/.daily_leads.lock ]; then
  P="$(tr -d '[:space:]' < data/.daily_leads.lock/pid 2>/dev/null)"
  if [ -n "$P" ] && kill -0 "$P" 2>/dev/null; then
    echo "  ⛔ Tageslauf AKTIV (PID $P)"; frei=1
  else
    echo "  ⚠ verwaister Lock (PID '${P:-?}' läuft nicht) — der Tageslauf übernimmt ihn selbst"
  fi
else
  echo "  ✓ kein Lock"
fi

echo "── goVisor-Prozesse ──"
# `index-docs`/`docworker` schreiben nach data/docs, `cli gold|silver|ingest` nach data/gold
# bzw. data/silver. Beides sind Kollisionen, nur an verschiedenen Stellen.
#
# ⚠ `ps auxww`, NICHT `ps aux`. Ohne Terminal schneidet macOS die Befehlszeile bei 80 Zeichen
# ab — und der Python-Pfad
# (/Library/Frameworks/Python.framework/…/MacOS/Python) ist allein schon ~95 Zeichen lang.
# Das Wort „govisor" faellt also genau weg, und die Pruefung meldete „keine Prozesse",
# waehrend `index-docs` seit 76 Minuten lief. Ein Fehlalarm in Richtung „Bahn frei" ist der
# einzige, den dieses Skript nicht machen darf. Gemessen und behoben am 2026-08-15.
#
# ⚠ UND: erst einsammeln, dann pruefen — NIEMALS `ps … | grep -q`. `grep -q` steigt beim
# ersten Treffer aus, `ps` bekommt SIGPIPE, und mit `set -o pipefail` wird die Pipeline zu
# Exit 141. Das `if` nimmt dann den else-Zweig: „keine Prozesse" — WEIL etwas gefunden wurde.
# Diese Fassung hat mir „Bahn frei" gemeldet, waehrend `index-docs` seit 76 Minuten lief.
# ⚠ UND: nicht nur `govisor.` — das trifft `python -m govisor.…` und sonst nichts. Die
# beiden DAUER-Arbeiter (`dokumente_arbeiter.sh`, `analyse_arbeiter.sh`) laufen als
# Bash-Skript, ihre Befehlszeile enthaelt `govisor/` mit Schraegstrich, nicht mit Punkt.
# Ausgerechnet sie liefen am 2026-08-21 seit zwei Tagen — und diese Pruefung meldete
# „keine Prozesse". Sie sind die wahrscheinlichste Kollision ueberhaupt, weil sie nie enden.
#
# Die Klammern um den ersten Buchstaben halten grep davon ab, sich selbst zu finden.
# ⚠ UND: `python3 scripts/<irgendwas>.py` MITZAEHLEN. Bis zum 2026-08-25 stand hier nur
# `govisor.` (mit Punkt) plus drei Skriptnamen. Ein von Hand gestartetes
# `python3 scripts/export_web_leads.py` oder `scripts/analyze_docs.py` — beides schreibt
# nach `data/` bzw. `web/data/` — fiel durch jedes dieser Muster und die Pruefung meldete
# „Bahn frei". Ausgerechnet Handlaeufe sind der Grund, warum es dieses Skript gibt.
# Verlangt wird der Interpreter DAVOR (`… /Python scripts/x.py`) — sonst schlaegt die
# Pruefung schon bei einem Editor an, der den Dateinamen im Titel fuehrt, und eine
# Pruefung, die staendig grundlos anschlaegt, liest bald niemand mehr.
_proc="$(ps -Ao pid=,command= | grep -E '[g]ovisor\.|[Pp]ython[0-9.]* +[^ ]*scripts/[a-z_]+\.py|[d]okumente_arbeiter|[a]nalyse_arbeiter|[d]aily_leads' || true)"
if [ -n "$_proc" ]; then
  # Zeichen vor JEDE Zeile — `printf %s` mit mehrzeiliger Variable setzt es nur vor die
  # erste, der Rest sieht dann aus wie Fliesstext und wird ueberlesen.
  echo "$_proc" | sed 's|/[^ ]*/Python ||' | cut -c1-110 | head -8 | sed 's/^/  ⛔ /'
  frei=1
else
  echo "  ✓ keine"
fi

echo "── frische Schreibzugriffe (letzte 5 min) ──"
n="$(find data/docs data/gold data/silver -mmin -5 -type f 2>/dev/null | wc -l | tr -d ' ')"
if [ "${n:-0}" -gt 0 ]; then
  find data/docs data/gold data/silver -mmin -5 -type f 2>/dev/null | head -3 | sed 's/^/  ⛔ /'
  echo "  ⛔ $n Dateien — da arbeitet jemand"
  frei=1
else
  echo "  ✓ nichts"
fi

# Halb geschriebene Zwischenstände sind ein Kollisionszeichen, auch ohne laufenden Prozess.
tmp="$(find data -maxdepth 3 \( -name '*.neu' -o -name '*.neu.parquet' -o -name '*.teil' \) 2>/dev/null | head -3)"
if [ -n "$tmp" ]; then
  echo "── Zwischenstände ──"; echo "$tmp" | sed 's/^/  ⚠ /'
  echo "  ⚠ deutet auf einen laufenden oder abgebrochenen Schreibvorgang hin"
  frei=1
fi

echo
if [ "$frei" -eq 0 ]; then echo "✅ Bahn frei."; else echo "⛔ NICHT starten — erst abwarten."; fi
exit "$frei"
