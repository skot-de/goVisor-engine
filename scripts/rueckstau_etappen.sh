#!/usr/bin/env bash
# Rueckstau-Abbau in Etappen, mit Qualitaetsschranke dazwischen.
#
# Sven, 2026-08-24: „lass den rueckstau abarbeiten bis das budget leer ist, aber setz alle
# 5 oder 10 $ qualitygates."
#
# Eine Etappe gibt `ETAPPE_USD` aus und haelt selbst an (BUDGET_USD in analyze_docs misst
# die Kontodifferenz). Danach zieht `scripts/qualitaetsschranke.py` sieben Kennzahlen und
# vergleicht sie mit der Voretappe. Rot heisst: HIER wird angehalten, nicht weitergefahren.
#
# ⚠ WARUM DIE SCHRANKE ANHALTEN MUSS UND NICHT NUR WARNEN. Der Abbau laeuft stundenlang
# unbeaufsichtigt. Eine Verschlechterung, die nur ins Log schreibt, produziert bis zum
# naechsten Hinsehen tausende schlechter Analysen — und die kosten mehr als die Etappe, die
# man sich spart. Am 2026-08-24 lief `:floor` bei 304 von 311 Aufrufen ins Leere, 48 % zu
# viel gezahlt, und der Kontostand fiel dabei voellig plausibel.
#
# ⚠ PARALLEL BEWUSST 8, NICHT 40. Die Geldwache prueft in Abstaenden; bei 40 gleichzeitigen
# Anfragen sind im Moment des Abbruchs bis zu 40 unterwegs. Gemessen: mit 8 stoppten die
# Etappen bei 10,16 und 10,11 $ gegen ein 10-$-Ziel — rund 1 % daneben.
#
# Aufruf:
#   scripts/rueckstau_etappen.sh                 # bis das Guthaben den Boden erreicht
#   ETAPPEN=3 ETAPPE_USD=5 scripts/rueckstau_etappen.sh
set -u
cd "$(dirname "$0")/.."

ETAPPE_USD="${ETAPPE_USD:-10}"
ETAPPEN="${ETAPPEN:-99}"
# Unter diesem Guthaben wird nicht mehr begonnen. Reserve (1,00) plus Schonung (0,50) plus
# eine Etappe — sonst startet ein Lauf, der sofort in die Geldwache faellt.
BODEN="${BODEN:-$(python3 -c "print(1.5 + ${ETAPPE_USD})")}"
LOG="data/logs/etappen-$(date +%Y%m%d-%H%M).log"
mkdir -p data/logs

sag() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

sag "Etappen-Abbau: je ${ETAPPE_USD} \$, hoechstens ${ETAPPEN}, Boden ${BODEN} \$"

for ((i = 1; i <= ETAPPEN; i++)); do
  if pgrep -f "scripts/analyze_docs.py" >/dev/null; then
    sag "⛔ Es laeuft bereits eine Analyse — abgebrochen."; exit 1
  fi
  stand=$(python3 -c "import sys;sys.path.insert(0,'.');from govisor import llm;print(f'{llm.kontostand() or 0:.2f}')" 2>/dev/null | tail -1)
  if python3 -c "import sys; sys.exit(0 if float('$stand') < float('$BODEN') else 1)"; then
    sag "Guthaben ${stand} \$ unter dem Boden ${BODEN} \$ — Schluss."; exit 0
  fi
  sag "── Etappe ${i}: ${ETAPPE_USD} \$ (Guthaben ${stand} \$)"

  BUDGET_USD="$ETAPPE_USD" \
  GOVISOR_LIMIT_USD="$(python3 -c "print(${ETAPPE_USD} + 1)")" \
  GOVISOR_TAG_USD="${GOVISOR_TAG_USD:-200}" \
  PARALLEL="${PARALLEL:-8}" LIMIT="${LIMIT:-600}" NUR_OFFENE=1 PYTHONUNBUFFERED=1 \
    python3 -u scripts/analyze_docs.py >>"$LOG" 2>&1
  sag "   $(grep -oE 'Budget erreicht.*' "$LOG" | tail -1)"

  sag "── Schranke nach Etappe ${i}"
  if python3 scripts/qualitaetsschranke.py >>"$LOG" 2>&1; then
    sag "   ✓ gruen"
  else
    sag "   ⛔ ROT — Abbau angehalten. Befunde:"
    sed -n '/Qualitätsschranke ·/,/verlangen Hinsehen/p' "$LOG" | tail -12 | tee -a "$LOG"
    exit 2
  fi
done
sag "Alle ${ETAPPEN} Etappen durch."
