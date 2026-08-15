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
ROOT="/Users/svko_macmini/PROJEKTE/claude_code/C09_govisor"
cd "$ROOT" || exit 1
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
_proc="$(ps -Ao pid=,command= | grep 'govisor\.' || true)"
if [ -n "$_proc" ]; then
  printf '  ⛔ %s\n' "$(echo "$_proc" | sed 's|/[^ ]*/Python ||' | head -8)"
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
