#!/bin/bash
# Wartet, bis der Tageslauf beendet ist, und startet DANN den Index-Neuaufbau.
#
# Die Vorgaengerversion zaehlte Schleifendurchlaeufe (240 x 30 s) und rechnete damit,
# dass ein Durchlauf 30 s dauert. Unter Last brauchte jeder ~85 s, weil pro Runde ein
# python3 hochgefahren wurde — die "2-Stunden"-Grenze war real 5,5 h und haette den
# Neuaufbau am Ende NICHT gestartet, sondern abgebrochen. Jetzt wird die WANDUHR
# gemessen, nicht die Rundenzahl, und gewartet wird mit dem Shell-eigenen sleep.
cd "$(dirname "$0")/.." || exit 1
# ⚠ VOLLER PFAD, s. analyse_arbeiter.sh: unter launchd ist `python3` das System-Python
# ohne duckdb, und der Lauf scheitert stumm.
PY=/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
[ -x "$PY" ] || PY=python3
# Der Ort des Index-Protokolls — beide Nachlaufskripte lesen dieselbe Variable, statt
# sich getrennt auf `/tmp/index_neu4.log` zu einigen und beim Umbenennen zu zerfallen.
IXLOG="${IXLOG:-/tmp/govisor-index-neuaufbau.log}"
ENDE=$(( $(date +%s) + 10800 ))          # harte Obergrenze: 3 h
while pgrep -f "daily_leads.sh" >/dev/null; do
  if [ "$(date +%s)" -ge "$ENDE" ]; then
    echo "⚠ Tageslauf laeuft nach 3 h noch — Neuaufbau NICHT gestartet."; exit 1
  fi
  sleep 20
done
echo "Tageslauf beendet um $(date '+%H:%M:%S')"
# ⚠ Das JUENGSTE Tageslauf-Log, nicht ein eingetipptes Datum. Hier stand bis zum
# 2026-08-25 fest `daily-2026-08-15.log` — ab dem 16.08. also die letzten drei Zeilen
# eines Laufs von gestern oder gar nichts.
tail -3 "$(ls -t data/logs/daily-*.log 2>/dev/null | head -1)" 2>/dev/null

if ! mkdir data/.index_docs.lock 2>/dev/null; then
  echo "LOCK BELEGT — ein Index-Lauf ist schon aktiv, abgebrochen."; exit 1
fi
echo $$ > data/.index_docs.lock/pid
# Nur die EIGENE Sperre wegraeumen. Ein blindes `rm -rf` nimmt die Sperre eines
# Nachfolgers mit, wenn dieser Lauf spaet stirbt — dieselbe Falle wie im
# Analyse-Arbeiter, s. dort.
trap 'if [ "$(tr -d "[:space:]" < data/.index_docs.lock/pid 2>/dev/null)" = "$$" ]; then rm -rf data/.index_docs.lock; fi' EXIT

echo "--- Index-Neuaufbau startet $(date '+%H:%M:%S') ---"
GOVISOR_INDEX_ARBEITER=3 GOVISOR_ARBEITER_GB=2 \
  "$PY" -m govisor.cli index-docs --country DE --neu-aufbauen > "$IXLOG" 2>&1
echo "EXIT=$?  ($(date '+%H:%M:%S'))"
tail -8 "$IXLOG"
