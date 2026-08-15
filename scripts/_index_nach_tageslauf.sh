#!/bin/bash
# Wartet, bis der Tageslauf beendet ist, und startet DANN den Index-Neuaufbau.
#
# Die Vorgaengerversion zaehlte Schleifendurchlaeufe (240 x 30 s) und rechnete damit,
# dass ein Durchlauf 30 s dauert. Unter Last brauchte jeder ~85 s, weil pro Runde ein
# python3 hochgefahren wurde — die "2-Stunden"-Grenze war real 5,5 h und haette den
# Neuaufbau am Ende NICHT gestartet, sondern abgebrochen. Jetzt wird die WANDUHR
# gemessen, nicht die Rundenzahl, und gewartet wird mit dem Shell-eigenen sleep.
cd "$(dirname "$0")/.." || exit 1
ENDE=$(( $(date +%s) + 10800 ))          # harte Obergrenze: 3 h
while pgrep -f "daily_leads.sh" >/dev/null; do
  if [ "$(date +%s)" -ge "$ENDE" ]; then
    echo "⚠ Tageslauf laeuft nach 3 h noch — Neuaufbau NICHT gestartet."; exit 1
  fi
  sleep 20
done
echo "Tageslauf beendet um $(date '+%H:%M:%S')"
tail -3 data/logs/daily-2026-08-15.log

if ! mkdir data/.index_docs.lock 2>/dev/null; then
  echo "LOCK BELEGT — ein Index-Lauf ist schon aktiv, abgebrochen."; exit 1
fi
echo $$ > data/.index_docs.lock/pid
trap 'rm -rf data/.index_docs.lock' EXIT

echo "--- Index-Neuaufbau startet $(date '+%H:%M:%S') ---"
GOVISOR_INDEX_ARBEITER=3 GOVISOR_ARBEITER_GB=2 \
  python3 -m govisor.cli index-docs --country DE --neu-aufbauen > /tmp/index_neu4.log 2>&1
echo "EXIT=$?  ($(date '+%H:%M:%S'))"
tail -8 /tmp/index_neu4.log
