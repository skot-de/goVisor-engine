#!/usr/bin/env bash
# Zustand der Maschine, alle N Sekunden eine Zeile.
#
# ⚠ WARUM ES DAS GIBT. Seit dem 2026-09-09 traegt jede Protokollzeile eine Uhrzeit, und
# damit wurde sichtbar, was die Schrittzeiten verdeckt hatten: die Schritte sind nicht
# gleichmaessig langsam, sie STEHEN. Gemessen in der Nacht zum 2026-09-10:
#
#   simap.ch   50 Publikationen dauern 27 s — und dann viermal 15 bis 18 MINUTEN.
#   DÖE        ein Monat dauert 5 s — und dann einmal 16 min, einmal 11 min.
#   Kategorie  30 Titel dauern 4 s — und dann dreimal 28 bis 33 min.
#
# Dieselbe Arbeit, derselbe Rechner, Faktor 40. Und es trifft Netz-Schritte UND reine
# Rechenschritte gleichermassen — also liegt es nicht an den Gegenstellen.
#
# Was wir wissen: 16 GB RAM, 6,3 GB Auslagerung belegt, `data` liegt auf einer USB-SSD
# (gemessen ~68 MB/s), Chromium bekam einen Startzeitablauf nach 180 s. Was wir NICHT
# wissen: welcher davon zuschlaegt. Genau dafuer diese Datei.
#
# ⚠ Sie ersetzt kein Werkzeug, sie ueberlebt nur die Nacht. `top` und `Aktivitaets-
# anzeige` zeigen den Zustand JETZT — und um 03:21 sieht niemand hin.
set -u

ZIEL="${1:?Zieldatei angeben}"
TAKT="${2:-30}"

printf 'zeit\tload1\tswap_mb\tfrei_mb\tpageins_pro_s\n' > "$ZIEL"

VOR_PI=""
while :; do
  # Eine Abfrage je Kennzahl, keine Schleifen — der Mitschreiber selbst darf die Messung
  # nicht stoeren.
  LOAD=$(sysctl -n vm.loadavg | tr -d '{}' | awk '{print $1}')
  SWAP=$(sysctl -n vm.swapusage | awk '{sub("M","",$6); print $6}')
  # `vm_stat` nennt die Seitengroesse in der Kopfzeile — nicht 4096 annehmen, auf
  # Apple-Silicon sind es 16384.
  read -r FREI PI <<EOP
$(vm_stat | awk '
    /page size of/ { for (i=1;i<=NF;i++) if ($i ~ /^[0-9]+$/) ps=$i }
    /^Pages free/  { gsub("\\.","",$3); frei=$3 }
    /^Pageins/     { gsub("\\.","",$2); pi=$2 }
    END { printf "%d %d", frei*ps/1048576, pi }')
EOP
  if [ -n "$VOR_PI" ]; then
    PI_S=$(( (PI - VOR_PI) / TAKT ))
  else
    PI_S=0
  fi
  VOR_PI="$PI"
  printf '%s\t%s\t%s\t%s\t%s\n' "$(date '+%H:%M:%S')" "$LOAD" "$SWAP" "$FREI" "$PI_S" >> "$ZIEL"
  sleep "$TAKT"
done
