#!/bin/bash
# Wartet auf das Ende des Index-Neuaufbaus und legt DANN den Grundlauf der Signale.
#
# Warum ueberhaupt noch ein Voll-Lauf, wo der Schritt jetzt inkrementell ist: der
# Neuaufbau schreibt `doc_text.parquet` vollstaendig neu, also kippt JEDER Fingerabdruck.
# Das ist kein Defekt der Inkrementalitaet, sondern ihr korrektes Verhalten — neuer Text
# heisst neue Signale. Erst dieser Lauf legt den Merkzettel an, gegen den der morgige
# Tageslauf vergleichen kann.
cd "$(dirname "$0")/.." || exit 1
ENDE=$(( $(date +%s) + 21600 ))          # Obergrenze 6 h
while pgrep -f "cli index-docs" >/dev/null; do
  if [ "$(date +%s)" -ge "$ENDE" ]; then
    echo "⚠ Index-Neuaufbau laeuft nach 6 h noch — Signal-Grundlauf NICHT gestartet."; exit 1
  fi
  sleep 30
done
echo "Index-Neuaufbau beendet um $(date '+%H:%M:%S')"
tail -4 /tmp/index_neu4.log

echo "--- Signal-Grundlauf startet $(date '+%H:%M:%S') ---"
python3 -m govisor.cli signals-docs --country DE > /tmp/signale_grund.log 2>&1
echo "EXIT=$?  ($(date '+%H:%M:%S'))"
tail -4 /tmp/signale_grund.log
python3 scripts/export_doc_signals.py 2>&1 | tail -2
