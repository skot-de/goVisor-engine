#!/bin/bash
# Tauscht `daily_leads.sh` gegen die gehaertete Fassung — ERST wenn kein Lauf mehr aktiv ist.
#
# Warum nicht sofort: Bash liest ein laufendes Skript haeppchenweise nach. Wird die Datei
# unter ihm geaendert, verschiebt sich die Leseposition und der Rest des Laufs wird
# Kauderwelsch. Das ist kein theoretisches Risiko, sondern die Standard-Falle beim
# Bearbeiten laufender Shell-Skripte.
cd "$(dirname "$0")/.." || exit 1
ENDE=$(( $(date +%s) + 21600 ))
while pgrep -f "daily_leads.sh" >/dev/null; do
  [ "$(date +%s)" -ge "$ENDE" ] && { echo "⚠ Lauf laeuft nach 6 h noch — NICHT getauscht."; exit 1; }
  sleep 30
done
cp scripts/daily_leads.sh scripts/daily_leads.sh.vor-haertung
cp /tmp/dl_neu.sh scripts/daily_leads.sh
chmod +x scripts/daily_leads.sh
bash -n scripts/daily_leads.sh && echo "getauscht um $(date '+%H:%M:%S') · Syntax ok" \
  || { echo "⛔ Syntaxfehler — zurueckgerollt"; cp scripts/daily_leads.sh.vor-haertung scripts/daily_leads.sh; exit 1; }
grep -c 'mit_grenze "$GRENZE_ABRUF"' scripts/daily_leads.sh | sed 's/^/  Schritte unter Zeitgrenze: /'
