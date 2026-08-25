#!/usr/bin/env bash
# Ein Ort für „was läuft gerade und was sagt es?".
#
# Die Logs liegen an zwei Stellen, und das hat Gründe, die man sich nicht merken will:
#   data/logs/            die Läufe selbst (auf der externen Platte, mit den Daten)
#   ~/Library/Logs/       was launchd auffängt (data/ ist ein Symlink — launchd kommt
#                         dort beim Laden nicht hin, s. eu.govisor.dokumente.plist)
# Statt sich das zu merken: scripts/logs.sh
#
# ⚠ DER ANALYSE-ARBEITER HAT HIER GEFEHLT. Er wurde am 2026-08-18 aus dem Dokumenten-
# Arbeiter herausgeloest und bekam einen eigenen Dienst mit eigenem Log — diese Übersicht
# wusste bis zum 25.08. nichts davon. „Ein Ort für was läuft gerade" ist wertlos, wenn er
# einen von zwei Dauerläufern verschweigt: er sah einfach aus, als liefe er nicht.
#
# Aufruf:  scripts/logs.sh            Übersicht
#          scripts/logs.sh arbeiter   dem Dokumenten-Arbeiter zusehen
#          scripts/logs.sh analyse    dem Analyse-Arbeiter zusehen
#          scripts/logs.sh tag        dem Tageslauf zusehen
set -uo pipefail
cd "$(dirname "$0")/.."
case "${1:-uebersicht}" in
  arbeiter) exec tail -f data/logs/dokumente-arbeiter.log ;;
  analyse)  exec tail -f "$HOME/Library/Logs/govisor-analyse.log" ;;
  tag)      exec tail -f "$(ls -t data/logs/daily-*.log | head -1)" ;;
  uebersicht)
    echo
    echo "  LÄUFT GERADE"
    pgrep -f daily_leads >/dev/null && echo "    ▶ Tageslauf" || echo "    · Tageslauf schläft"
    pgrep -f dokumente_arbeiter >/dev/null && echo "    ▶ Dokumenten-Arbeiter" || echo "    · Dokumenten-Arbeiter schläft"
    pgrep -f analyse_arbeiter  >/dev/null && echo "    ▶ Analyse-Arbeiter"    || echo "    · Analyse-Arbeiter schläft"
    echo
    echo "  ZULETZT GESAGT — Arbeiter"
    tail -4 data/logs/dokumente-arbeiter.log 2>/dev/null | sed 's/^/    /' || echo "    (noch nichts)"
    echo
    echo "  ZULETZT GESAGT — Analyse"
    tail -3 "$HOME/Library/Logs/govisor-analyse.log" 2>/dev/null | cut -c1-96 | sed 's/^/    /'
    echo
    echo "  ZULETZT GESAGT — Tageslauf"
    tail -4 "$(ls -t data/logs/daily-*.log 2>/dev/null | head -1)" 2>/dev/null | cut -c1-96 | sed 's/^/    /'
    echo
    echo "  MITLESEN"
    echo "    scripts/logs.sh arbeiter     scripts/logs.sh analyse     scripts/logs.sh tag"
    echo "    scripts/dokumente_stand.py   (Trichter + Kosten)"
    echo ;;
  *) echo "arbeiter | analyse | tag | uebersicht" ;;
esac
